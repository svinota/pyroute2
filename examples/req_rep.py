from pyroute2.iocore.template import public
from pyroute2.iocore.template import Node


# define test echo server
class MyServer(Node):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)


# start server and client
url = 'tcp://localhost:9824/service'
node1 = MyServer()
node1.serve(url)

node2 = Node()
proxy = node2.connect(url)

# request echo call
print(proxy.echo('test'))
