import os
import uuid
import socket
from pyroute2 import IPRoute
from pyroute2.netlink import NetlinkError
from multiprocessing import Event
from multiprocessing import Process
from utils import grep
from utils import require_user
from utils import get_ip_addr
from utils import get_ip_link
from utils import get_ip_route
from utils import create_link
from utils import remove_link


def _run_remote_client(url, func, key=None, cert=None, ca=None):
    ip = IPRoute(host=url, key=key, cert=cert, ca=ca)
    getattr(ip, func)()
    ip.release()


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
        _assert_servers(ip, 0)
        _assert_clients(ip, 1)
        ip.serve(url, key=key, cert=cert, ca=ca)
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 1)
        _assert_clients(ip, 1)
        ip.shutdown_servers(url)
        _assert_uplinks(ip, 1)
        _assert_servers(ip, 0)
        _assert_clients(ip, 1)
        ip.shutdown_sockets()
        _assert_uplinks(ip, 0)
        _assert_servers(ip, 0)
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


class TestServerSide(object):

    def testServer(self):
        url = 'unix://\0%s' % (uuid.uuid4())
        ip = IPRoute()
        ip.serve(url)
        target = Process(target=_run_remote_client,
                         args=(url, 'get_links'))
        target.start()
        target.join()
        ip.release()


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


def _callback(msg, obj):
    obj.cb_counter += 1


class TestData(object):

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPRoute()
        self.dev = self.ip.link_lookup(ifname='dummyX')

    def teardown(self):
        self.ip.release()
        remove_link('dummyX')
        remove_link('bala')

    def test_add_addr(self):
        require_user('root')
        dev = self.dev[0]
        self.ip.addr('add', dev, address='172.16.0.1', mask=24)
        assert '172.16.0.1/24' in get_ip_addr()

    def test_remove_link(self):
        require_user('root')
        create_link('bala', 'dummy')
        dev = self.ip.link_lookup(ifname='bala')[0]
        try:
            self.ip.link_remove(dev)
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 0

    def test_route(self):
        require_user('root')
        create_link('bala', 'dummy')
        dev = self.ip.link_lookup(ifname='bala')[0]
        self.ip.link('set', index=dev, state='up')
        self.ip.addr('add', dev, address='172.16.0.2', mask=24)
        self.ip.route('add',
                      prefix='172.16.1.0',
                      mask=24,
                      gateway='172.16.0.1')
        assert grep('ip route show', pattern='172.16.1.0/24.*172.16.0.1')
        remove_link('bala')

    def test_updown_link(self):
        require_user('root')
        dev = self.dev[0]
        assert not (self.ip.get_links(dev)[0]['flags'] & 1)
        try:
            self.ip.link_up(dev)
        except NetlinkError:
            pass
        assert self.ip.get_links(dev)[0]['flags'] & 1
        try:
            self.ip.link_down(dev)
        except NetlinkError:
            pass
        assert not (self.ip.get_links(dev)[0]['flags'] & 1)

    def test_callbacks_positive(self):
        require_user('root')
        dev = self.dev[0]

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == dev,
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter > 0
        self.ip.unregister_callback(_callback)

    def test_callbacks_negative(self):
        require_user('root')

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == 'nonsence',
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter == 0
        self.ip.unregister_callback(_callback)

    def test_rename_link(self):
        require_user('root')
        dev = self.dev[0]
        try:
            self.ip.link_rename(dev, 'bala')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 1
        try:
            self.ip.link_rename(dev, 'dummyX')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='dummyX')) == 1

    def test_addr(self):
        assert len(get_ip_addr()) == len(self.ip.get_addr())

    def test_links(self):
        assert len(get_ip_link()) == len(self.ip.get_links())

    def test_one_link(self):
        lo = self.ip.get_links(1)[0]
        assert lo.get_attr('IFLA_IFNAME') == 'lo'

    def test_routes(self):
        assert len(get_ip_route()) == \
            len(self.ip.get_routes(family=socket.AF_INET, table=255))


class TestRemoteData(TestData):

    def setup(self):
        create_link('dummyX', 'dummy')
        url = 'unix://\0%s' % (uuid.uuid4())
        allow_connect = Event()
        target = Process(target=_run_remote_uplink,
                         args=(url, allow_connect))
        target.daemon = True
        target.start()
        allow_connect.wait()
        self.ip = IPRoute(host=url)
        self.dev = self.ip.link_lookup(ifname='dummyX')


class TestSSLData(TestData):
    ssl_proto = 'ssl'

    def setup(self):
        create_link('dummyX', 'dummy')
        url = 'unix+%s://\0%s' % (self.ssl_proto, uuid.uuid4())
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
        self.dev = self.ip.link_lookup(ifname='dummyX')


class TestTLSData(TestSSLData):
    ssl_proto = 'tls'
