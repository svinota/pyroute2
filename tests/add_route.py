from pyroute2 import iproute
from pprint import pprint

ip = iproute()
pprint(ip.add_route('90.0.0.0', 24, gateway='10.0.0.1'))
