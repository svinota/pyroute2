#!/usr/bin/python
'''
Messaging node: "server" role.

Please note, that "server" or "client" role is not a
property of the node, it is just a way you use it.
'''
import sys
from pyroute2.rpc import Node
from pyroute2.rpc import public


class Namespace(object):
    '''
    Just a namespace to publish procedures
    '''
    @public
    def echo(self, msg):
        return '%s passed' % (msg)

node = Node()
node.register(Namespace())
node.serve('tcp://localhost:9824')
print(' hit Ctrl+D to exit ')
sys.stdin.read()
