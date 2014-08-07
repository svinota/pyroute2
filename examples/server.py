#!/usr/bin/python
'''
Sample server script.

Start netlink proxy on the port 7000 and use TLS client/server
authentication. Clients w/o known certificates will be rejected.

You have to generate keys prior to start it. The easiest way is
to use OpnVPN's pkitool
'''
import os
import sys
from pyroute2 import IPRoute

ip = IPRoute()

ip.serve('tls://localhost:7000',
         key='server.key',
         cert='server.crt',
         ca='ca.crt')


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

ip.release()
