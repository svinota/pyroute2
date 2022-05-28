from pyroute2 import NDB
from pyroute2.common import uifname

# unique interface names
vlan_host = uifname()
vlan_interface = uifname()

with NDB() as ndb:


    (
        ndb.interfaces.create(ifname=vlan_host, kind='dummy')
        .set('state', 'up')
        .commit()
    )
    (
        ndb.interfaces.create(
            ifname=vlan_interface,
            kind='vlan',
            link=ndb.interfaces[vlan_host],
            vlan_id=101
        )
        .set('mtu', 1400)
        .set('state', 'up')
        .add_ip('10.251.0.1/24')
        .add_ip('10.251.0.2/24')
        .commit()
    )

    for i in (vlan_interface, vlan_host):
        ndb.interfaces[i].remove().commit()
