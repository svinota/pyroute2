#!/usr/bin/env python

import inspect
import json
from pyroute2 import DiagSocket

with DiagSocket() as ds:
    ds.bind()
    sstats = ds.get_sock_stats()

    for stat in sstats:
        #print inspect.getmembers(stat)
        print stat.get['UDIAG_SHOW_PEER']

#from socket import AF_INET
#from pyroute2 import IPRoute

## get access to the netlink socket
#ip = IPRoute()

## no monitoring here -- thus no bind()

## print interfaces
#print(ip.get_links())

#print json.dumps(sstats, indent=4)
