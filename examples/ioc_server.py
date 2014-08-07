#!/usr/bin/python
'''
Messaging node: "server" role.

Please note, that "server" or "client" role is not a
property of the node, it is just a way you use it.
'''
import os
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

##
# This code is needed just to wait a signal to exit -- either
# from keyboard, when the script is launched standalone, or
# from test suite
#
if 'pr2_sync' in __builtins__:
    os.read(__builtins__['pr2_sync'], 1)
else:
    print("Hit Ctrl-D to release IPRoute and exit")
    sys.stdin.read()


node.shutdown()
