from pyroute2 import iproute
from pprint import pprint

ip = iproute()
pprint(ip.add_addr(interface=1, address='127.0.0.10', mask=8))
