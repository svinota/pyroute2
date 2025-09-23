import errno
import resource
import socket

import pytest

from pyroute2 import AsyncIPRoute, IPRoute
from pyroute2.common import uifname
from pyroute2.netlink.nlsocket import NetlinkSocket


def _test_ports_auto():
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


def _test_ports_fail():
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
        resource.setrlimit(resource.RLIMIT_NOFILE, (10384, 10384))
    except ValueError:
        pytest.skip('cannot set RLIMIT_NOFILE')

    # create and bind 1024 sockets
    ports = [NetlinkSocket() for x in range(1025)]
    counter = 0
    with pytest.raises(KeyError):
        for port in ports:
            port.bind()
            counter += 1

    assert 0 < counter <= 180
    assert 20 < ports[counter].status['port'] < 200

    # cleanup
    for port in ports:
        port.close()

    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


@pytest.mark.asyncio
async def test_enobufs_async(async_ipr, nsname):
    ifname: str = uifname()
    ifaddr: str = '172.16.3.2'
    dst: str = '10.3.4.0'
    gateway: str = '172.16.3.10'
    # Create a socket and start receiving broadcasts
    ipr = AsyncIPRoute(netns=nsname, rcvbuf=1024)
    await ipr.bind()
    # Make some netlink trafic
    await async_ipr.link('add', ifname=ifname, kind='dummy', state='up')
    (link,) = await async_ipr.poll(
        async_ipr.link, 'dump', ifname=ifname, state='up', timeout=2
    )
    await async_ipr.addr(
        'add', index=link.get('index'), address=f'{ifaddr}/24'
    )
    (addr,) = await async_ipr.poll(
        async_ipr.addr, 'dump', address=f'{ifaddr}', timeout=2
    )
    await async_ipr.route('add', dst=f'{dst}/24', gateway=f'{gateway}')
    (route,) = await async_ipr.poll(
        async_ipr.route, 'dump', dst=f'{dst}', timeout=2
    )
    assert route.get('oif') == link.get('index')
    await async_ipr.link('del', index=link.get('index'))

    with pytest.raises(OSError) as e:
        [x async for x in ipr.get()]
    assert e.value.errno == errno.ENOBUFS


def test_enobufs_sync(sync_ipr, nsname):
    ifname: str = uifname()
    ifaddr: str = '172.16.3.2'
    dst: str = '10.3.4.0'
    gateway: str = '172.16.3.10'
    # Create a socket and start receiving broadcasts
    ipr = IPRoute(netns=nsname, rcvbuf=1024)
    ipr.bind()
    # Make some netlink trafic
    sync_ipr.link('add', ifname=ifname, kind='dummy', state='up')
    (link,) = sync_ipr.poll(
        sync_ipr.link, 'dump', ifname=ifname, state='up', timeout=2
    )
    sync_ipr.addr('add', index=link.get('index'), address=f'{ifaddr}/24')
    (addr,) = sync_ipr.poll(
        sync_ipr.addr, 'dump', address=f'{ifaddr}', timeout=2
    )
    sync_ipr.route('add', dst=f'{dst}/24', gateway=f'{gateway}')
    (route,) = sync_ipr.poll(sync_ipr.route, 'dump', dst=f'{dst}', timeout=2)
    assert route.get('oif') == link.get('index')
    sync_ipr.link('del', index=link.get('index'))

    with pytest.raises(OSError) as e:
        ipr.get()
    assert e.value.errno == errno.ENOBUFS
