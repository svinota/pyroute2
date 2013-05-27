import os
import uuid
import socket
from pyroute2 import iproute
from multiprocessing import Event
from multiprocessing import Process
# test imports
from utils import get_ip_addr
from utils import get_ip_link
from utils import get_ip_route


def _run_remote_uplink(url, allow_connect):
    ip = iproute()
    ip.iothread.allow_rctl = True
    ip.serve(url)
    allow_connect.set()
    ip.iothread._stop_event.wait()


def _assert_servers(ip, num):
    assert len(ip.get_servers()) == num
    assert len(ip.iothread.servers) == num


def _assert_clients(ip, num):
    assert len(ip.get_clients()) == num
    assert len(ip.iothread.clients) == num


def _assert_uplinks(ip, num):
    assert len(ip.get_sockets()) == num
    assert len(ip.iothread.uplinks) == num


class TestSetup(object):

    def test_simple(self):
        ip = iproute()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)

    def test_noautoconnect(self):
        ip = iproute(do_connect=False)
        _assert_uplinks(ip, 0)
        ip.connect()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)

    def test_serve(self):
        url = 'unix://\0nose_tests_socket'
        ip = iproute()
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 1)
        _assert_clients(ip, 1)
        ip.serve(url)
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 2)
        _assert_clients(ip, 1)
        ip.shutdown_servers(url)
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 1)
        _assert_clients(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)
        _assert_servers(ip, 1)
        _assert_clients(ip, 1)


class TestSetupUplinks(object):

    def _test_remote(self, url):
        allow_connect = Event()
        target = Process(target=_run_remote_uplink,
                         args=(url, allow_connect))
        target.daemon = True
        target.start()
        allow_connect.wait()
        ip = iproute(host=url)
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)

    def test_unix_abstract_remote(self):
        self._test_remote('unix://\0nose_tests_socket')

    def test_unix_remote(self):
        sck = './nose_tests_socket'
        url = 'unix://' + sck
        try:
            os.remove(sck)
        except OSError as e:
            if e.errno != 2:  # no such file or directory
                raise e
        self._test_remote(url)

    def test_tcp_remote(self):
        self._test_remote('tcp://127.0.0.1:9821')


class TestData(object):
    ip = None

    def setup(self):
        self.ip = iproute()

    def teardown(self):
        self.ip.shutdown_sockets()

    def test_addr(self):
        assert len(get_ip_addr()) == len(self.ip.get_addr())

    def test_links(self):
        assert len(get_ip_link()) == len(self.ip.get_links())

    def test_routes(self):
        assert len(get_ip_route()) == \
            len(self.ip.get_routes(family=socket.AF_INET, table=255))


class TestRemoteData(TestData):

    def setup(self):
        url = 'unix://\0%s' % (uuid.uuid4())
        allow_connect = Event()
        target = Process(target=_run_remote_uplink,
                         args=(url, allow_connect))
        target.daemon = True
        target.start()
        allow_connect.wait()
        self.ip = iproute(host=url)
