import time
from pyroute2.netlink import IPRCMD_STOP
from pyroute2.netlink import IPRCMD_RELOAD
from pyroute2.netlink import IPRCMD_SUBSCRIBE
from pyroute2.iocore import NLT_DGRAM
from pyroute2.rpc import public
from pyroute2.rpc import Node
from pyroute2 import IOCore
from pyroute2 import TimeoutError


class TestIOBroker(object):

    def setup(self):
        self.ioc1 = IOCore(secret='bala')
        self.ioc1.serve('tcp://localhost:9824')
        self.ioc2 = IOCore()
        self.host = self.ioc2.connect('tcp://localhost:9824')
        self.ioc2.register('bala', self.host[1])

    def teardown(self):
        self.ioc2.release()
        self.ioc1.release()

    def test_err_connect(self):
        try:
            self.ioc1.connect('tcp://localhost:404')
        except RuntimeError:
            pass

    def test_err_discover(self):
        try:
            self.ioc1.discover('non_existent')
        except RuntimeError:
            pass

    def _test_stop(self):
        #
        # FIXME
        #
        # this test stopped to work properly after the
        # broker became a separate process
        self.ioc2.command(IPRCMD_STOP, addr=self.host[1])

    def test_reload(self):
        self.ioc2.command(IPRCMD_RELOAD, addr=self.host[1])

    def test_provide_remove(self):
        self.ioc2.provide('/dala')
        self.ioc2.remove('/dala')

    def test_fail_access(self):
        self.ioc2.unregister(self.host[1])
        try:
            self.ioc2.command(IPRCMD_STOP, addr=self.host[1])
        except RuntimeError:
            pass
        self.ioc2.register('bala', self.host[1])

    def test_fail_disconnect(self):
        try:
            self.ioc2.disconnect('invalid_uid')
        except RuntimeError:
            pass

    def test_fail_connect(self):
        try:
            self.ioc2.connect('unix://\0invalid_socket')
        except RuntimeError:
            pass

    def test_fail_subscribe(self):
        try:
            self.ioc2.command(IPRCMD_SUBSCRIBE)
        except RuntimeError:
            pass


class Namespace(object):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)

    @public
    def sleep(self, t):
        time.sleep(t)

    @public
    def error(self):
        raise RuntimeError('test exception')


class TestPush(object):

    def setup(self):
        self.url_tcp = 'tcp://0.0.0.0:9823/push'
        self.url_udp = 'udp://0.0.0.0:9823/push'
        self.node1 = Node()
        self.node1.serve(self.url_tcp)
        self.node1.serve(self.url_udp)
        self.node1.mirror()
        self.node2 = Node()

    def teardown(self):
        self.node2.shutdown()
        self.node1.shutdown()

    def test_tcp_push(self):
        proxy = self.node2.target(self.url_tcp)
        proxy.push('test1')
        assert self.node1.get() == b'test1'

    def test_udp_push(self):
        proxy = self.node2.target(self.url_tcp, self.url_udp, NLT_DGRAM)
        proxy.push('test2')
        assert self.node1.get() == b'test2'


class TestMessaging(object):

    def setup(self):
        url = 'unix://\0one_test_socket/service'
        self.node1 = Node(serve=url)
        self.node1.register(Namespace())

        self.node2 = Node()
        self.proxy = self.node2.connect(url, timeout=1)

    def teardown(self):
        self.node2.shutdown()
        self.node1.shutdown()

    def test_req_rep(self):
        assert self.proxy.echo('test') == b'test passed'

    def test_timeout_fail(self):
        try:
            self.proxy.sleep(2)
            raise Exception("Timeout isn't reached")
        except TimeoutError:
            pass

    def test_timeout_ok(self):
        self.proxy._timeout = 10
        self.proxy.sleep(2)

    def test_exception(self):
        try:
            self.proxy.error()
        except RuntimeError:
            pass
