import ctypes
import ctypes.util
import re
import subprocess

import pytest
from pr2test.context_manager import skip_if_not_supported
from pr2test.marks import require_root

from pyroute2 import protocols
from pyroute2.netlink.rtnl import TC_H_INGRESS

pytestmark = [require_root()]


def get_bpf_syscall_num():
    # determine bpf syscall number
    prog = """
#include <asm/unistd.h>
#define XSTR(x) STR(x)
#define STR(x) #x
#pragma message "__NR_bpf=" XSTR(__NR_bpf)
"""
    cmd = ['gcc', '-x', 'c', '-c', '-', '-o', '/dev/null']
    gcc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    out = gcc.communicate(input=prog.encode('ascii'))[1]
    m = re.search('__NR_bpf=([0-9]+)', str(out))
    if not m:
        pytest.skip('bpf syscall not available')
    return int(m.group(1))


def get_simple_bpf_program(prog_type):
    NR_bpf = get_bpf_syscall_num()

    class BPFAttr(ctypes.Structure):
        _fields_ = [
            ('prog_type', ctypes.c_uint),
            ('insn_cnt', ctypes.c_uint),
            ('insns', ctypes.POINTER(ctypes.c_ulonglong)),
            ('license', ctypes.c_char_p),
            ('log_level', ctypes.c_uint),
            ('log_size', ctypes.c_uint),
            ('log_buf', ctypes.c_char_p),
            ('kern_version', ctypes.c_uint),
        ]

    BPF_PROG_TYPE_SCHED_CLS = 3
    BPF_PROG_TYPE_SCHED_ACT = 4
    BPF_PROG_LOAD = 5
    insns = (ctypes.c_ulonglong * 2)()
    # equivalent to: int my_func(void *) { return 1; }
    insns[0] = 0x00000001000000B7
    insns[1] = 0x0000000000000095
    license = ctypes.c_char_p(b'GPL')
    if prog_type.lower() == "sched_cls":
        attr = BPFAttr(
            BPF_PROG_TYPE_SCHED_CLS, len(insns), insns, license, 0, 0, None, 0
        )
    elif prog_type.lower() == "sched_act":
        attr = BPFAttr(
            BPF_PROG_TYPE_SCHED_ACT, len(insns), insns, license, 0, 0, None, 0
        )
    libc = ctypes.CDLL(ctypes.util.find_library('c'))
    libc.syscall.argtypes = [
        ctypes.c_long,
        ctypes.c_int,
        ctypes.POINTER(type(attr)),
        ctypes.c_uint,
    ]
    libc.syscall.restype = ctypes.c_int
    fd = libc.syscall(NR_bpf, BPF_PROG_LOAD, attr, ctypes.sizeof(attr))
    return fd


@pytest.fixture
def bpf_cls():
    fd = get_simple_bpf_program('sched_cls')
    if fd == -1:
        pytest.skip('bpf syscall error')
    yield fd


@pytest.fixture
def bpf_act():
    fd = get_simple_bpf_program('sched_act')
    if fd == -1:
        pytest.skip('bpf syscall error')
    yield fd


@pytest.fixture
def ingress(context):
    context.ipr.tc(
        'add',
        kind='ingress',
        index=context.default_interface.index,
        handle=0xFFFF0000,
    )
    yield context


@skip_if_not_supported
def test_simple(ingress):
    qds = [
        x
        for x in ingress.ipr.get_qdiscs()
        if x['index'] == ingress.default_interface.index
    ]
    # assert the list is not empty
    assert qds
    # assert there is the ingress queue
    for qd in qds:
        if qd.get_attr('TCA_KIND') == 'ingress':
            # assert it has proper handle and parent
            assert qd['handle'] == 0xFFFF0000
            assert qd['parent'] == TC_H_INGRESS
            break
    else:
        raise Exception('no ingress qdisc found')


@skip_if_not_supported
def test_filter_sched_cls(ingress, bpf_cls):
    ingress.ipr.tc(
        'add-filter',
        kind='bpf',
        index=ingress.default_interface.index,
        handle=0,
        fd=bpf_cls,
        name='my_func',
        parent=0xFFFF0000,
        action='ok',
        classid=1,
        rate='10kbit',
        burst=10240,
        mtu=2040,
    )
    fls = ingress.ipr.get_filters(
        index=ingress.default_interface.index, parent=0xFFFF0000
    )
    # assert the supplied policer is returned to us intact
    plcs = [
        x
        for x in fls
        if x.get_attr('TCA_OPTIONS') is not None
        and (x.get_attr('TCA_OPTIONS').get_attr('TCA_BPF_POLICE') is not None)
    ][0]
    options = plcs.get_attr('TCA_OPTIONS')
    police = options.get_attr('TCA_BPF_POLICE').get_attr('TCA_POLICE_TBF')
    assert police['rate'] == 1250
    assert police['mtu'] == 2040


@skip_if_not_supported
def test_filter_sched_act(ingress, bpf_cls, bpf_act):
    index, ifname = ingress.default_interface
    ingress.ipr.tc(
        'add-filter',
        'bpf',
        index=index,
        handle=0,
        fd=bpf_cls,
        name='my_func',
        parent=0xFFFF0000,
        action='ok',
        classid=1,
    )
    action = {'kind': 'bpf', 'fd': bpf_act, 'name': 'my_func', 'action': 'ok'}
    ingress.ipr.tc(
        'add-filter',
        'u32',
        index=index,
        handle=1,
        protocol=protocols.ETH_P_ALL,
        parent=0xFFFF0000,
        target=0x10002,
        keys=['0x0/0x0+0'],
        action=action,
    )
    fls = ingress.ipr.get_filters(index=index, parent=0xFFFF0000)
    assert fls
    bpf_filter = [
        x
        for x in fls
        if x.get_attr('TCA_OPTIONS') is not None
        and (x.get_attr('TCA_OPTIONS').get_attr('TCA_BPF_ACT') is not None)
    ][0]
    bpf_options = bpf_filter.get_attr('TCA_OPTIONS')
    assert bpf_options.get_attr('TCA_BPF_NAME') == 'my_func'
    gact_parms = (
        bpf_options.get_attr('TCA_BPF_ACT')
        .get_attr('TCA_ACT_PRIO_1')
        .get_attr('TCA_ACT_OPTIONS')
        .get_attr('TCA_GACT_PARMS')
    )
    assert gact_parms['action'] == 0


@skip_if_not_supported
def test_filter_delete(context, bpf_cls):
    context.ipr.tc('add', kind='clsact', index=context.default_interface.index)
    context.ipr.tc(
        'add-filter',
        kind='bpf',
        index=context.default_interface.index,
        fd=bpf_cls,
        name='my_func',
        parent='ffff:fff2',
        classid=1,
        direct_action=True,
    )
    filters = context.ipr.get_filters(
        index=context.default_interface.index, parent='ffff:fff2'
    )
    # len == 2: handles 0 and 1
    assert len(filters) == 2
    context.ipr.tc(
        'del-filter',
        kind='bpf',
        index=context.default_interface.index,
        parent='ffff:fff2',
        info=filters[0]['info'],
    )
    filters = context.ipr.get_filters(
        index=context.default_interface.index, parent='ffff:fff2'
    )
    assert len(filters) == 0
