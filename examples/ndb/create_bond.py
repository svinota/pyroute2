from pyroute2 import NDB
from pyroute2.common import uifname

# create unique interface names
p0 = uifname()
p1 = uifname()
bond = uifname()

with NDB() as ndb:


    # The same scheme works for bridge interfaces too: you
    # can create a bridge interface and assign ports to it
    # just as below.
    ndb.interfaces.create(kind='dummy', ifname=p0).commit()
    ndb.interfaces.create(kind='dummy', ifname=p1).commit()

    with ndb.interfaces.create(kind='bond', ifname=bond) as i:
        # assign two interfaces
        i.add_port(p0)
        i.add_port(p0)
        # make an example more scary: add IPs
        i.add_ip('10.251.0.1/24')
        i.add_ip('10.251.0.2/24')

    for i in (p0, p1, bond):
        ndb.interfaces[i].remove().commit()
