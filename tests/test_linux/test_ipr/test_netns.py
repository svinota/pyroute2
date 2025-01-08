import ctypes
import errno
import os

import pytest
from pr2test.marks import require_root

from pyroute2 import NetNS

pytestmark = [require_root()]


def test_flags(context):
    nsname = context.new_nsname
    with pytest.raises(FileNotFoundError) as e:
        NetNS(nsname, flags=0)
    assert e.value.args[0] == errno.ENOENT
    # 8<-----------------------------------------------------
    ns = NetNS(nsname, flags=os.O_CREAT)
    assert len([x.get('index') for x in ns.link('dump')]) > 0
    ns.close()
    # 8<-----------------------------------------------------
    ns = NetNS(nsname, flags=0)
    assert len([x.get('index') for x in ns.link('dump')]) > 0
    ns.close()


def test_libc_id(context):
    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    nsname = context.new_nsname
    ns = NetNS(nsname, libc=libc)
    assert id(ns.asyncore.libc) == id(libc)
    ns.close()


def test_libc_fail_string(context):
    nsname = context.new_nsname
    with pytest.raises(AttributeError):
        # if we pass a string instead of a libc object, the
        # libc.mount() must fail with AttributeError
        NetNS(nsname, libc='nonsense')


def test_get_netns_info(context):
    nsname = context.new_nsname
    peer_name = context.new_ifname
    host_name = context.new_ifname
    with NetNS(nsname):
        (
            context.ndb.interfaces.create(
                ifname=host_name,
                kind='veth',
                peer={'ifname': peer_name, 'net_ns_fd': nsname},
            ).commit()
        )
        # get veth
        veth = context.ipr.link('get', ifname=host_name)[0]
        target = veth.get_attr('IFLA_LINK_NETNSID')
        for info in context.ipr.get_netns_info():
            path = info.get_attr('NSINFO_PATH')
            if path.endswith(nsname):
                netnsid = info['netnsid']
                if target == netnsid:
                    break
        else:
            raise KeyError('peer netns not found')
