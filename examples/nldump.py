#!/usr/bin/python
'''
Slightly more complicate example, than trace_ip_link.
'''
import sys
from pyroute2 import IPRoute
from Queue import Empty
from pprint import pprint

if len(sys.argv) < 2:
    print 'choose program to run, e.g.:'
    print '%s ip link show' % (sys.argv[0])
    sys.exit(0)

ip = IPRoute()
q = ip.connect('ptrace://%s' % ' '.join(sys.argv[1:]), no_stdout=True)
while True:
    try:
        pprint(ip.get(q, do_raise=False))
    except Empty:
        break
