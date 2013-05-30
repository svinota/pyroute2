import os
import uuid
import socket
from pyroute2 import IPRoute
from multiprocessing import Event
from multiprocessing import Process
# test imports
from utils import get_ip_addr
from utils import get_ip_link
from utils import get_ip_route


def _run_remote_uplink(url, allow_connect, key=None, cert=None, ca=None):
    ip = IPRoute()
    ip.serve(url, key=key, cert=cert, ca=ca)
    allow_connect.set()
    ip.iothread._stop_event.wait()
    ip.release()


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
        ip = IPRoute()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)
        ip.release()

    def test_noautoconnect(self):
        ip = IPRoute(do_connect=False)
        _assert_uplinks(ip, 0)
        ip.connect()
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)
        ip.release()

    def test_serve(self, url=None, key=None, cert=None, ca=None):
        url = url or 'unix://\0nose_tests_socket'
        ip = IPRoute()
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 1)
        _assert_clients(ip, 1)
        ip.serve(url, key=key, cert=cert, ca=ca)
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
        ip.release()

    def test_serve_ssl(self):
        url = 'ssl://127.0.0.1:9876'
        key = 'server.key'
        cert = 'server.crt'
        ca = 'ca.crt'
        return self.test_serve(url, key, cert, ca)

    def test_serve_unix_ssl(self):
        url = 'unix+ssl://\0nose_tests_socket'
        key = 'server.key'
        cert = 'server.crt'
        ca = 'ca.crt'
        return self.test_serve(url, key, cert, ca)


class TestSetupUplinks(object):

    def _test_remote(self, url):
        allow_connect = Event()
        target = Process(target=_run_remote_uplink,
                         args=(url, allow_connect))
        target.daemon = True
        target.start()
        allow_connect.wait()
        ip = IPRoute(host=url)
        _assert_uplinks(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)
        ip.release()

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
        try:
            os.remove(sck)
        except OSError as e:
            if e.errno != 2:
                raise e

    def test_tcp_remote(self):
        self._test_remote('tcp://127.0.0.1:9821')


class TestData(object):

    def setup(self):
        self.ip = IPRoute()

    def teardown(self):
        self.ip.release()

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
        self.ip = IPRoute(host=url)


class TestSSLData(TestData):

    def setup(self):
        url = 'unix+ssl://\0%s' % (uuid.uuid4())
        allow_connect = Event()
        target = Process(target=_run_remote_uplink,
                         args=(url,
                               allow_connect,
                               'server.key',
                               'server.crt',
                               'ca.crt'))
        target.daemon = True
        target.start()
        allow_connect.wait()
        self.ip = IPRoute(host=url,
                          key='client.key',
                          cert='client.crt',
                          ca='ca.crt')
