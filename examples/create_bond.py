'''
Example: python ./examples/create_bond.py

Creates bond interface.
'''
from pyroute2 import IPDB
from pyroute2.common import uifname

ip = IPDB()

try:

    # create unique interface names
    p0 = uifname()
    p1 = uifname()
    ms = uifname()

    # The same scheme works for bridge interfaces too: you
    # can create a bridge interface and enslave some ports
    # to it just as below.
    ip.create(kind='dummy', ifname=p0).commit()
    ip.create(kind='dummy', ifname=p1).commit()

    with ip.create(kind='bond', ifname=ms) as i:
        # enslave two interfaces
        i.add_port(ip.interfaces[p0])
        i.add_port(ip.interfaces[p1])
        # make an example more scary: add IPs
        i.add_ip('10.251.0.1/24')
        i.add_ip('10.251.0.2/24')

finally:
    for i in (p0, p1, ms):
        try:
            ip.interfaces[i].remove().commit()
        except:
            pass
    ip.release()
