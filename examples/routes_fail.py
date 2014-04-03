'''
Simple sequence to reproduce an error with IPRoute/IPDB/IOCore
interference. Gets reproduced in ~5%
'''
from pyroute2 import IPDB

ip = IPDB()
with ip.routes.add({'dst': '172.16.0.0/24',
                    'gateway': '192.168.122.2'}) as r:
    pass

with ip.routes['172.16.0.0/24'] as r:
    r.gateway = '192.168.122.1'

with ip.routes['172.16.0.0/24'] as r:
    r.remove()
