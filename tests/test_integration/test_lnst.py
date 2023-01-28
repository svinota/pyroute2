import select

import pytest

# NetlinkError, NetlinkDecodeError
# IPRoute
# IPRSocket
from pyroute2 import IPRoute as IPRoute0
from pyroute2 import IPRSocket as IPRSocket0
from pyroute2 import NetlinkDecodeError as NetlinkDecodeError0
from pyroute2 import NetlinkError as NetlinkError0
from pyroute2.iproute import IPRoute as IPRoute1

# nlmsg
# flags
from pyroute2.netlink import (
    NLM_F_DUMP,
    NLM_F_MATCH,
    NLM_F_REQUEST,
    NLM_F_ROOT,
    NLMSG_DONE,
    NLMSG_ERROR,
)
from pyroute2.netlink import NetlinkDecodeError as NetlinkDecodeError1
from pyroute2.netlink import NetlinkError as NetlinkError1
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl import (
    RTM_DELADDR,
    RTM_DELLINK,
    RTM_GETADDR,
    RTM_GETLINK,
    RTM_NEWADDR,
    RTM_NEWLINK,
    RTMGRP_IPV4_IFADDR,
    RTMGRP_IPV6_IFADDR,
    RTMGRP_LINK,
)
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.iprsocket import IPRSocket as IPRSocket1
from pyroute2.netlink.rtnl.rtmsg import rtmsg


def test_exceptions_compat():

    with pytest.raises(NetlinkError1):
        raise NetlinkError1(code=99)

    with pytest.raises(NetlinkDecodeError1):
        raise NetlinkDecodeError1(exception=Exception())


def test_exceptions():

    with pytest.raises(NetlinkError0):
        raise NetlinkError0(code=99)

    with pytest.raises(NetlinkDecodeError0):
        raise NetlinkDecodeError0(exception=Exception())


def test_constants():
    assert issubclass(ifinfmsg, nlmsg)
    assert NLM_F_REQUEST == 1
    assert NLM_F_ROOT == 0x100
    assert NLM_F_MATCH == 0x200
    assert NLM_F_DUMP == (NLM_F_ROOT | NLM_F_MATCH)
    assert NLMSG_DONE == 0x3
    assert NLMSG_ERROR == 0x2
    assert RTM_NEWLINK == 0x10
    assert RTM_DELLINK == 0x11
    assert RTM_GETLINK == 0x12
    assert RTM_NEWADDR == 0x14
    assert RTM_DELADDR == 0x15
    assert RTM_GETADDR == 0x16
    assert RTMGRP_LINK == 0x1
    assert RTMGRP_IPV4_IFADDR == 0x10
    assert RTMGRP_IPV6_IFADDR == 0x100


@pytest.mark.parametrize('socket_class', (IPRSocket0, IPRSocket1))
def test_basic(socket_class):

    ip = socket_class()
    ip.bind()

    # check the `socket` interface compliance
    poll = select.poll()
    poll.register(ip, select.POLLIN | select.POLLPRI)
    poll.unregister(ip)
    ip.close()


@pytest.mark.parametrize('iproute_class', (IPRoute0, IPRoute1))
def test_iproute_message_classes(iproute_class):
    with iproute_class() as ip:
        assert {ifaddrmsg, ifinfmsg, rtmsg} < {type(x) for x in ip.dump()}


@pytest.mark.parametrize('iproute_class', (IPRoute0, IPRoute1))
def test_iproute_message_subclass(iproute_class):
    with iproute_class() as ip:
        assert all([issubclass(type(x), nlmsg) for x in ip.dump()])


@pytest.mark.parametrize('iprsocket_class', (IPRSocket0, IPRSocket1))
def test_iprsocket_put(iprsocket_class):
    NL_GROUPS = RTMGRP_IPV4_IFADDR | RTMGRP_IPV6_IFADDR | RTMGRP_LINK
    with iprsocket_class() as iprs:
        iprs.bind(groups=NL_GROUPS)
        iprs.put(None, RTM_GETLINK, msg_flags=NLM_F_REQUEST | NLM_F_DUMP)
