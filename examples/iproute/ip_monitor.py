'''
Simplest example to monitor Netlink events with a Python script.
'''

from pprint import pprint

from pyroute2 import IPRSocket

ip = IPRSocket()
ip.bind()
pprint(ip.get())
ip.close()
