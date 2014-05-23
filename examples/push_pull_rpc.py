'''
Push/pull using RPC
'''
from pyroute2.rpc import Node

# create the first endpoint, serve two sockets
node1 = Node()
node1.serve('tcp://0.0.0.0:9824/push')
node1.mirror()

# create the second endpoint, connect via TCP
node2 = Node()
proxy1 = node2.target('tcp://0.0.0.0:9824/push')
proxy1.push('hello, world!')

# wait the message on the first endpoint
print('waiting message from client')
msg = node1.get()
print(msg)

node2.shutdown()
node1.shutdown()
