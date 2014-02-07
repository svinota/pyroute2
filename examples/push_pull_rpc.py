'''
Push/pull using RPC
'''
from pyroute2.rpc import Node

# create the first endpoint, serve two sockets
ioc1 = Node()
ioc1.serve('tcp://0.0.0.0:9824/push')
ioc1.mirror()

# create the second endpoint, connect via TCP
ioc2 = Node()
proxy1 = ioc2.target('tcp://0.0.0.0:9824/push')
proxy1.push('hello, world!')

# wait the message on the first endpoint
print('waiting message from client')
msg = ioc1.get()
print(msg)

ioc2.shutdown()
ioc1.shutdown()
