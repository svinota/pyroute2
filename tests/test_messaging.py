import uuid
from pyroute2.iocore.template import public
from pyroute2.iocore.template import Node


class Namespace(object):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)

    @public
    def error(self):
        raise RuntimeError('test exception')


class TestMessaging(object):

    def setup(self):
        url = 'unix://\0%s/service' % (uuid.uuid4())
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
