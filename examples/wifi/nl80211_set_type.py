from pyroute2 import IW, IPRoute
from pyroute2.netlink.exceptions import NetlinkError

# interface name to check
ifname = 'wlx2'
iftype = 'monitor'

iw = IW()
ip = IPRoute()
index = ip.link_lookup(ifname=ifname)[0]
try:
    print(f"Original type: '{iw.get_interface_type(index)}'")
    iw.set_interface_type(index, iftype)
    print(f"New state: '{iw.get_interface_type(index)}'")
except NetlinkError as e:
    print(f"Exception : {e}")
finally:
    iw.close()
    ip.close()
