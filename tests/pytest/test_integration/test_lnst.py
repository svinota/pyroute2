import pytest
import select

# IPRSocket
from pyroute2 import IPRSocket as IPRSocket0
from pr2modules.netlink.rtnl.iprsocket import IPRSocket as IPRSocket1
from pyroute2.netlink.rtnl.iprsocket import IPRSocket as IPRSocket2

# IPRoute
from pyroute2 import IPRoute as IPRoute0
from pr2modules.iproute import IPRoute as IPRoute1
from pyroute2.iproute import IPRoute as IPRoute2

# NetlinkError, NetlinkDecodeError
from pyroute2 import NetlinkError as NetlinkError0
from pyroute2 import NetlinkDecodeError as NetlinkDecodeError0
from pyroute2.netlink import NetlinkError as NetlinkError1
from pyroute2.netlink import NetlinkDecodeError as NetlinkDecodeError1

# flags
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_ROOT
from pyroute2.netlink import NLM_F_MATCH
from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.iproute import RTM_GETLINK
from pyroute2.iproute import RTM_NEWLINK

# nlmsg
from pyroute2.netlink import nlmsg
from pr2modules.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pr2modules.netlink.rtnl.ifinfmsg import ifinfmsg
from pr2modules.netlink.rtnl.rtmsg import rtmsg


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


@pytest.mark.parametrize('socket_class', (IPRSocket0, IPRSocket1, IPRSocket2))
def test_basic(socket_class):

    ip = socket_class()
    ip.bind()

    # check the `socket` interface compliance
    poll = select.poll()
    poll.register(ip, select.POLLIN | select.POLLPRI)
    poll.unregister(ip)
    ip.close()

    assert issubclass(ifinfmsg, nlmsg)
    assert NLM_F_REQUEST == 1
    assert NLM_F_ROOT == 0x100
    assert NLM_F_MATCH == 0x200
    assert NLM_F_DUMP == (NLM_F_ROOT | NLM_F_MATCH)
    assert NLMSG_DONE == 0x3
    assert NLMSG_ERROR == 0x2
    assert RTM_GETLINK == 0x12
    assert RTM_NEWLINK == 0x10


@pytest.mark.parametrize('iproute_class', (IPRoute0, IPRoute1, IPRoute2))
def test_iproute_message_classes(iproute_class):
    with iproute_class() as ip:
        assert {ifaddrmsg, ifinfmsg, rtmsg} < {type(x) for x in ip.dump()}


@pytest.mark.parametrize('iproute_class', (IPRoute0, IPRoute1, IPRoute2))
def test_iproute_message_subclass(iproute_class):
    with iproute_class() as ip:
        assert all([issubclass(type(x), nlmsg) for x in ip.dump()])
