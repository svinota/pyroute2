import errno
from pyroute2 import IW
from pyroute2 import IPRoute
from pyroute2.netlink.exceptions import NetlinkError

# interface name to check
ifname = 'lo'

ip = IPRoute()
iw = IW()
index = ip.link_lookup(ifname=ifname)[0]
try:
    iw.get_interface_by_ifindex(index)
    print("wireless interface")
except NetlinkError as e:
    if e.code == errno.ENODEV:  # 19 'No such device'
        print("not a wireless interface")
finally:
    iw.close()
    ip.close()
