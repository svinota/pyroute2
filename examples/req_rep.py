from pyroute2.iocore.template import public
from pyroute2.iocore.template import Server
from pyroute2.iocore.template import Client


# define test echo server
class MyServer(Server):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)


# start server and client
url = 'tcp://localhost:9824/service'
s = MyServer(url)
c = Client(url)

# request echo call
print(c.echo('test'))
