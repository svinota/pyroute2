import socket
from utils import require_user
from pyroute2.netlink.nlsocket import NetlinkSocket


class TestNL(object):

    def test_ports_auto(self):
        # create two sockets
        s1 = NetlinkSocket()
        s2 = NetlinkSocket()

        # both bind() should succeed
        s1.bind()
        s2.bind()

        # check that ports are different
        assert s1.port != s2.port

        s1.close()
        s2.close()

    def test_ports_fail(self):
        s1 = NetlinkSocket(port=0x10)
        s2 = NetlinkSocket(port=0x10)

        # check if ports are set
        assert s1.port == s2.port

        # bind the first socket, must succeed
        s1.bind()

        # bind the second, must fail
        try:
            s2.bind()
        except socket.error as e:
            # but it must fail only with errno == 98
            if e.errno == 98:
                pass

        # check the first socket is bound
        assert s1.getsockname()[0] != 0
        # check the second socket is not bound
        assert s2.getsockname()[0] == 0

        s1.close()

    def test_no_free_ports(self):
        require_user('root')
        # create and bind 1024 sockets
        ports = [NetlinkSocket() for x in range(1024)]
        for port in ports:
            port.bind()

        # create an extra socket
        fail = NetlinkSocket()
        try:
            # bind must fail with KeyError: no free ports available
            fail.bind()
        except KeyError:
            pass

        # cleanup
        for port in ports:
            port.close()

        try:
            # failed socket shouldn't permit close()
            fail.close()
        except AssertionError:
            pass
