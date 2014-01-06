from pyroute2.iocore.template import public
from pyroute2.iocore.template import Server
from pyroute2.iocore.template import Client


class MyServer(Server):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)


class TestMessaging(object):

    def test_req_rep(self):
        url = 'tcp://localhost:9824/service'
        MyServer(url)
        c = Client(url)

        assert c.echo('test') == 'test passed'
