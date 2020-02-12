import pprint
import sys

from pyroute2.netlink.generic.ethtool import NlEthtool

if len(sys.argv) != 2:
    raise Exception("USAGE: {0} IFNAME".format(sys.argv[0]))


IFNAME = sys.argv[1]
eth = NlEthtool()

print("kernel ok?:", eth.is_nlethtool_in_kernel())
pprint.pprint(eth.get_linkmode(IFNAME))
print("")
pprint.pprint(eth.get_linkinfo(IFNAME))
print("")
pprint.pprint(eth.get_stringset(IFNAME))
print("")
pprint.pprint(eth.get_linkstate(IFNAME))
print("")
pprint.pprint(eth.get_wol(IFNAME))
