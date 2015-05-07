import select


class TestLnst(object):

    def test_issubclass(self):
        from pyroute2 import IPRSocket
        from pyroute2 import IPRoute
        from pyroute2 import IPDB
        from pyroute2.iproute import IPRoute as IPRoute_real
        from pyroute2.netlink.rtnl.iprsocket import IPRSocket as IPRSocket_real

        assert issubclass(IPRoute, IPRSocket)
        assert issubclass(IPRoute_real, IPRSocket_real)
        assert not issubclass(IPRoute, IPDB)
        assert not issubclass(IPRSocket, IPRoute)
        assert not issubclass(IPRSocket_real, IPRoute_real)

        # mixed environments are not supported, so do not run
        # assertion on real and proxied classes in one statement:
        # assert issubclass(IPRoute, IPRSocket_real)  # will *not* work
        # assert issubclass(IPRoute_real, IPRSocket)  # *may* work

    def test_isinstance(self):
        from pyroute2 import IPRSocket
        from pyroute2 import IPRoute
        from pyroute2.iproute import IPRoute as IPRoute_real
        from pyroute2.netlink.rtnl.iprsocket import IPRSocket as IPRSocket_real

        ipr1 = IPRoute()
        ipr2 = IPRoute_real()

        ips1 = IPRSocket()
        ips2 = IPRSocket_real()

        # positive
        assert isinstance(ips1, IPRSocket)
        assert isinstance(ips2, IPRSocket)
        assert isinstance(ips1, IPRSocket_real)
        assert isinstance(ips2, IPRSocket_real)

        assert isinstance(ipr1, IPRoute)
        assert isinstance(ipr2, IPRoute)
        assert isinstance(ipr1, IPRoute_real)
        assert isinstance(ipr2, IPRoute_real)

        # negative
        assert not isinstance(ips1, IPRoute)
        assert not isinstance(ips2, IPRoute)
        assert not isinstance(ips1, IPRoute_real)
        assert not isinstance(ips2, IPRoute_real)

        # this must succeed -- IPRoute is a subclass of IPRSocket
        assert isinstance(ipr1, IPRSocket)
        assert isinstance(ipr2, IPRSocket)
        assert isinstance(ipr1, IPRSocket_real)
        assert isinstance(ipr2, IPRSocket_real)

        ips1.close()
        ips2.close()
        ipr1.close()
        ipr2.close()

    def test_basic(self):
        from pyroute2 import IPRSocket
        from pyroute2.netlink import NLM_F_REQUEST
        from pyroute2.netlink import NLM_F_DUMP
        from pyroute2.netlink import NLM_F_ROOT
        from pyroute2.netlink import NLM_F_MATCH
        from pyroute2.netlink import NLMSG_DONE
        from pyroute2.netlink import NLMSG_ERROR
        from pyroute2.netlink import nlmsg
        from pyroute2.iproute import RTM_GETLINK
        from pyroute2.iproute import RTM_NEWLINK
        from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

        ip = IPRSocket()
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
