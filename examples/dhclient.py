import sys
from pprint import pprint
from pyroute2.dhcp.dhcp4socket import DHCP4Socket

if len(sys.argv) > 1:
    iface = sys.argv[1]
else:
    iface = 'eth0'
s = DHCP4Socket(iface)
s.put()
print("DHCP response:\n")
pprint(s.get())
