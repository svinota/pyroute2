#!/usr/bin/python

from pprint import pprint
from pyroute2 import IPRoute
from pyroute2 import IPDB
from pyroute2.common import uifname

# high-level interface
ipdb = IPDB()

interface = ipdb.create(ifname=uifname(), kind='dummy').\
    commit().\
    add_ip('172.16.0.1/24').\
    add_ip('172.16.0.2/24').\
    commit()

# low-level interface just to get raw messages
ip = IPRoute()
a = [x for x in ip.get_addr() if x['index'] == interface['index']]
print('\n8<--------------------- left operand')
pprint(a[0])
print('\n8<--------------------- right operand')
pprint(a[1])
print('\n8<--------------------- complement')
pprint(a[0] - a[1])
print('\n8<--------------------- intersection')
pprint(a[0] & a[1])

interface.remove().commit()

ip.close()
ipdb.release()
