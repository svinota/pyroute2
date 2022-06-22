import pytest
from pr2test.context_manager import skip_if_not_supported
from pr2test.marks import require_root
from utils import get_simple_bpf_program

from pyroute2.netlink.rtnl import TC_H_INGRESS

pytestmark = [require_root()]


@pytest.fixture
def bpf():
    fd = get_simple_bpf_program('sched_cls')
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
def test_filter_policer(ingress, bpf):
    ingress.ipr.tc(
        'add-filter',
        kind='bpf',
        index=ingress.default_interface.index,
        handle=0,
        fd=bpf,
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
def test_filter_delete(context, bpf):
    context.ipr.tc('add', kind='clsact', index=context.default_interface.index)
    context.ipr.tc(
        'add-filter',
        kind='bpf',
        index=context.default_interface.index,
        fd=bpf,
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
