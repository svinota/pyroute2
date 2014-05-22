from pyroute2 import IPDB

ip = IPDB()

# create a route
with ip.routes.add({'dst': '172.16.0.0/24',
                    'gateway': '192.168.122.2'}) as r:
    pass

# modify it
with ip.routes['172.16.0.0/24'] as r:
    r.gateway = '192.168.122.1'

# remove
with ip.routes['172.16.0.0/24'] as r:
    r.remove()

ip.release()
