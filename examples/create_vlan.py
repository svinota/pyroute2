'''
Example: python ./examples/create_vlan.py [master]

Master is an interface to add VLAN to, e.g. eth0 or tap0 or
whatever else. Without parameters use tap0 as the default.
'''
import sys
from pyroute2 import IPDB

ip = IPDB()

try:
    if len(sys.argv) == 2:
        # Get master interface from the command line
        master = ip[sys.argv[1]]['index']
    else:
        # Or use tap0 interface as an example
        master = ip.interfaces.tap0.index
        # or the same: master = ip.interfaces['tap0']['index']

    with ip.create(kind='vlan', ifname='v101', link=master, vlan_id=101) as i:
        # Arguments for ip.create() are executed before the transaction,
        # in the IPRoute.link('add', ...) call. If create() fails, the
        # interface became invalid and is not operable, you can safely
        # drop it.
        #
        # Here goes the rest of transaction. If it fails, the interface
        # continues to work, only failed transaction gets dropped.
        i.add_ip('10.251.0.1', 24)
        i.add_ip('10.251.0.2', 24)
        i.mtu = 1400

finally:
    ip.release()
