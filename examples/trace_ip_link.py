#!/usr/bin/python
'''
Launch external command 'ip link show' and analyze
netlink traffic, that it sends/receives. Just like
tcpdump, but for netlink protocol.
'''
import sys
from pyroute2 import IPRoute
from Queue import Empty
from pprint import pprint

ip = IPRoute()
q = ip.connect('ptrace://' + ' '.join(sys.argv[1:]))
while True:
    try:
        pprint(ip.get(q, raw=True))
    except Empty:
        break
