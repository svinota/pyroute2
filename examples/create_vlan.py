from pyroute2 import ipdb

ip = ipdb()

try:
    master = ip.tap0.index  # or the same: master = ip['tap0']['index']

    with ip.create(kind='vlan', ifname='v101', link=master, vlan_id=101) as i:
        i.add_ip('10.251.0.1', 24)
        i.add_ip('10.251.0.2', 24)
        i.mtu = 1400

finally:
    ip.shutdown()
