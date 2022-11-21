from inspect import signature

import pytest

import pyroute2
from pyroute2 import netlink, netns
from pyroute2.netlink import exceptions, rtnl
from pyroute2.netlink.rtnl import ifinfmsg, ndmsg


def parameters(func):
    try:
        return set(signature(func).parameters.keys())
    except ValueError:
        pytest.skip('ginature check error, skip test')


def test_imports():
    assert parameters(pyroute2.NetNS) > set(('netns', 'flags', 'libc'))
    assert signature(pyroute2.IPRoute)
    assert issubclass(netlink.NetlinkError, Exception)
    assert issubclass(exceptions.NetlinkDumpInterrupted, Exception)
    assert netlink.NetlinkError == exceptions.NetlinkError
    assert netlink.nla_slot
    assert netlink.nla_base
    assert parameters(rtnl.rt_scope.get) == set(('key', 'default'))
    assert isinstance(rtnl.rt_proto, dict) and 'static' in rtnl.rt_proto
    assert parameters(netns._create) == set(('netns', 'libc', 'pid'))
    assert parameters(netns.remove) == set(('netns', 'libc'))
    assert parameters(netns.listnetns) == set(('nspath',))
    assert ifinfmsg.IFF_ALLMULTI == 0x200
    assert {state[1]: state[0] for state in ndmsg.states.items()} == {
        0: 'none',
        1: 'incomplete',
        2: 'reachable',
        4: 'stale',
        8: 'delay',
        16: 'probe',
        32: 'failed',
        64: 'noarp',
        128: 'permanent',
    }
