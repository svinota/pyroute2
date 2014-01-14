#!/usr/bin/python
'''
Messaging node: "client" role
'''
from pyroute2.rpc import Node

node = Node()
proxy = node.connect('tcp://localhost:9824')
print(proxy.echo('test'))
