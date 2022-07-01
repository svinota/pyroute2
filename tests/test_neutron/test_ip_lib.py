from inspect import signature

import pyroute2
from pyroute2 import netlink, netns
from pyroute2.netlink import exceptions, rtnl
from pyroute2.netlink.rtnl import ifinfmsg, ndmsg


def parameters(func):
    return set(signature(func).parameters.keys())


def test_imports():
    assert parameters(pyroute2.NetNS) > set(('netns', 'flags', 'libc'))
    assert signature(pyroute2.IPRoute)
    assert issubclass(netlink.NetlinkError, Exception)
    assert issubclass(exceptions.NetlinkDumpInterrupted, Exception)
    assert netlink.NetlinkError == exceptions.NetlinkError
    assert netlink.nla_slot
    assert netlink.nla_base
    assert parameters(rtnl.rt_scope.get) == set(('key', 'default'))
    assert isinstance(rtnl.rt_proto, dict) and 'proto' in rtnl.rt_proto
    assert parameters(netns._create) == set(('netns', 'libc', 'pid'))
    assert parameters(netns.remove) == set(('netns', 'libc'))
    assert parameters(netns.listnetns) == set(('nspath'))
    assert issubclass(ifinfmsg, netlink.nlmsg)
    assert issubclass(ndmsg, netlink.nlmsg)
