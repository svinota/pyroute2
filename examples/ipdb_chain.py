# An example how to use command chaining in IPDB

from pyroute2 import IPDB

ip = IPDB()
# create slave ports
ip.create(ifname='bo0p0', kind='dummy').commit()
ip.create(ifname='bo0p1', kind='dummy').commit()
# set up bonding
ip.create(ifname='bo0', kind='bond', bond_mode=2).\
    add_port(ip.interfaces.bo0p0).\
    add_port(ip.interfaces.bo0p1).\
    add_ip('172.16.0.1/24').\
    add_ip('172.16.0.2/24').\
    option('mtu', 1400).\
    up().\
    commit()
