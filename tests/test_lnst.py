import socket


class TestLnst(object):

    def test_imports(self):
        from pyroute2 import IPRSocket
        from pyroute2.netlink import NLM_F_REQUEST
        from pyroute2.netlink import NLM_F_DUMP
        from pyroute2.netlink import NLM_F_ROOT
        from pyroute2.netlink import NLM_F_MATCH
        from pyroute2.netlink import NLMSG_DONE
        from pyroute2.netlink import NLMSG_ERROR
        from pyroute2.netlink import nlmsg
        from pyroute2.netlink.iproute import RTM_GETLINK
        from pyroute2.netlink.iproute import RTM_NEWLINK
        from pyroute2.netlink.proto.rtnl.ifinfmsg import ifinfmsg

        ip = IPRSocket()
        ip.bind()
        ip.close()

        assert issubclass(IPRSocket, socket.socket)
        assert issubclass(ifinfmsg, nlmsg)
        assert NLM_F_REQUEST == 1
        assert NLM_F_ROOT == 0x100
        assert NLM_F_MATCH == 0x200
        assert NLM_F_DUMP == (NLM_F_ROOT | NLM_F_MATCH)
        assert NLMSG_DONE == 0x3
        assert NLMSG_ERROR == 0x2
        assert RTM_GETLINK == 0x12
        assert RTM_NEWLINK == 0x10
