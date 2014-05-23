from pyroute2.rpc import public
from pyroute2.rpc import Node


# define test echo server
class Namespace(object):

    @public
    def echo(self, msg):
        return '%s passed' % (msg)


# start server and client
url = 'tcp://localhost:9824/service'
node1 = Node()
node1.register(Namespace())
node1.serve(url)

node2 = Node()
proxy = node2.connect(url)

# request echo call
print(proxy.echo('test'))

node1.shutdown()
node2.shutdown()
