#!/usr/bin/python
'''
Sample client script.

Connects to a netlink proxy on the port 7000 useng TLS.

You have to generate keys prior to start it. The easiest way is
to use OpnVPN's pkitool
'''

from pyroute2 import iproute
from pprint import pprint

ip = iproute(host='tls://localhost:7000',
             key='client.key',
             cert='client.crt',
             ca='ca.crt',
             interruptible=True)

pprint(ip.get_addr())
