from pyroute2 import iproute
from pprint import pprint

ip = iproute()
pprint(ip.get_all_routes())
