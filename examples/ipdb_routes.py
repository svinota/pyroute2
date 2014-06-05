from pyroute2 import IPDB

ip = IPDB()

# create dummy interface to host routes on
ip.create(kind='dummy', ifname='pr2test').\
    add_ip('172.16.1.1/24').\
    up().\
    commit()

# create a route
with ip.routes.add({'dst': '172.16.0.0/24',
                    'gateway': '172.16.1.2'}) as r:
    pass

# modify it
with ip.routes['172.16.0.0/24'] as r:
    r.gateway = '172.16.1.3'

# cleanup
with ip.routes['172.16.0.0/24'] as r:
    r.remove()

ip.interfaces.pr2test.remove().commit()

ip.release()
