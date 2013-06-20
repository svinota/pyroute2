#!/usr/bin/python
'''
Slightly more complicate example, than trace_ip_link.
'''
import sys
from pyroute2 import IPRoute
from Queue import Empty

if len(sys.argv) < 2:
    print 'choose program to run, e.g.:'
    print '%s ip link show' % (sys.argv[0])
    sys.exit(0)

ip = IPRoute(debug=True)
q = ip.connect('ptrace://%s' % ' '.join(sys.argv[1:]), no_stdout=True)
while True:
    try:
        for msg in ip.get(q, raw=True):
            print(msg)
    except Empty:
        break
