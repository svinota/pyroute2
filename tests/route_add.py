from pyroute2 import iproute
from pprint import pprint

ip = iproute()
pprint(ip.route_add('90.0.0.0', 24, gateway='10.0.0.1'))
