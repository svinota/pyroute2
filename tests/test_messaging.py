from pyroute2.iocore import NLT_DGRAM
from pyroute2.rpc import public
from pyroute2.rpc import Node


class Namespace(object):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)

    @public
    def error(self):
        raise RuntimeError('test exception')


class TestPush(object):

    def setup(self):
        url_tcp = 'tcp://0.0.0.0:9823/push'
        url_udp = 'udp://0.0.0.0:9823/push'
        self.node1 = Node()
        self.node1.serve(url_tcp)
        self.node1.serve(url_udp)
        self.node1.mirror()

        self.node2 = Node()
        self.proxy_tcp = self.node2.target(url_tcp)
        self.proxy_udp = self.node2.target(url_tcp, url_udp, NLT_DGRAM)

    def teardown(self):
        self.node2.shutdown()
        self.node1.shutdown()

    def test_tcp_push(self):
        self.proxy_tcp.push('test1')
        assert self.node1.get() == 'test1'

    def test_udp_push(self):
        self.proxy_udp.push('test2')
        assert self.node1.get() == 'test2'


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
        assert self.proxy.echo('test') == 'test passed'

    def test_exception(self):
        try:
            self.proxy.error()
        except RuntimeError:
            pass
