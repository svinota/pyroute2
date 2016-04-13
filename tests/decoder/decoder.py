#!/usr/bin/python
'''
Usage::

    ./decoder.py [module] [data_file]

Sample::

    ./decoder.py pyroute2.netlink.rtnl.tcmsg.tcmsg ./sample_packet_01.data
    ./decoder.py pyroute2.netlink.nl80211.nl80211cmd ./nl80211.data

Module is a name within rtnl hierarchy. File should be a
binary data in the escaped string format (see samples).
'''
import sys
from pprint import pprint
from importlib import import_module
from pyroute2.common import load_dump
from pyroute2.common import hexdump

mod = sys.argv[1]
mod = mod.replace('/', '.')
f = open(sys.argv[2], 'r')
s = mod.split('.')
package = '.'.join(s[:-1])
module = s[-1]
m = import_module(package)
met = getattr(m, module)


data = load_dump(f)

offset = 0
inbox = []
while offset < len(data):
    msg = met(data[offset:])
    msg.decode()
    print(hexdump(msg.raw))
    pprint(msg)
    print('.'*40)
    offset += msg['header']['length']
