'''
Simplest example to monitor Netlink events with a Python script.
'''

from pyroute2 import IPRSocket
from pprint import pprint

ip = IPRSocket()
ip.bind()
pprint(ip.get())
ip.close()
