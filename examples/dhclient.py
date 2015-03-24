from pprint import pprint
from pyroute2.dhcp import DHCP4Socket
s = DHCP4Socket('dhcp-if2')
s.put()
print("DHCP response:\n")
pprint(s.get())
