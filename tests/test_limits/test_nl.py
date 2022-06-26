import pytest
import socket
import resource
from pyroute2.netlink.nlsocket import NetlinkSocket


def test_ports_auto():
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


def test_ports_fail():
    s1 = NetlinkSocket(port=0x10)
    s2 = NetlinkSocket(port=0x10)

    # check if ports are set
    assert s1.port == s2.port

    # bind the first socket, must succeed
    s1.bind()

    # bind the second, must fail
    exception = None
    with pytest.raises(socket.error) as exception:
        s2.bind()
    # socket.error / OSError(98, 'Address already in use')
    assert exception.value.errno == 98

    s1.close()
    s2.close()


def test_no_free_ports():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
    except ValueError:
        pytest.skip('cannot set RLIMIT_NOFILE')

    # create and bind 1024 sockets
    ports = [NetlinkSocket() for x in range(1024)]
    for port in ports:
        port.bind()

    # create an extra socket
    fail = NetlinkSocket()
    # bind must fail with KeyError: no free ports available
    with pytest.raises(KeyError):
        fail.bind()

    # cleanup
    for port in ports:
        port.close()

    fail.close()
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
