from pyroute2.netlink import IPRCMD_STOP
from pyroute2.netlink import IPRCMD_RELOAD
from pyroute2.netlink import IPRCMD_SUBSCRIBE
from pyroute2.iocore import NLT_DGRAM
from pyroute2.rpc import public
from pyroute2.rpc import Node
from pyroute2 import IOCore


class TestIOBroker(object):

    def setup(self):
        self.ioc1 = IOCore()
        self.ioc1.iobroker.secret = 'bala'
        self.ioc1.serve('tcp://localhost:9824')
        self.ioc2 = IOCore()
        self.host = self.ioc2.connect('tcp://localhost:9824')
        self.ioc2.register('bala', self.host[1])

    def teardown(self):
        self.ioc2.release()
        self.ioc1.release()

    def test_stop(self):
        self.ioc2.command(IPRCMD_STOP, addr=self.host[1])
        assert self.ioc1.iobroker._stop_event.is_set()

    def test_reload(self):
        self.ioc2.command(IPRCMD_RELOAD, addr=self.host[1])

    def test_provide_remove(self):
        self.ioc2.provide('/dala')
        self.ioc2.remove('/dala')

    def test_fail_disconnect(self):
        try:
            self.ioc2.disconnect('invalid_uid')
        except AssertionError:
            pass

    def test_fail_connect(self):
        try:
            self.ioc2.connect('unix://\0invalid_socket')
        except AssertionError:
            pass

    def test_fail_subscribe(self):
        try:
            self.ioc2.command(IPRCMD_SUBSCRIBE)
        except AssertionError:
            pass


class Namespace(object):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)

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
        self.node1 = Node()
        self.node1.register(Namespace())
        self.node1.serve(url)

        self.node2 = Node()
        self.proxy = self.node2.connect(url)

    def teardown(self):
        self.node2.shutdown()
        self.node1.shutdown()

    def test_req_rep(self):
        assert self.proxy.echo('test') == b'test passed'

    def test_exception(self):
        try:
            self.proxy.error()
        except RuntimeError:
            pass
