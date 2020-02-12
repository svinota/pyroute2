import sys
from pyroute2.ethtool import Ethtool

if len(sys.argv) != 2:
    raise Exception("USAGE: {0} IFNAME".format(sys.argv[0]))
ethtool = Ethtool()
ifname = sys.argv[1]

print(ethtool.get_link_mode(ifname))
print(ethtool.get_link_info(ifname))
print(ethtool.get_strings_set(ifname))
print(ethtool.get_wol(ifname))
print(ethtool.get_features(ifname))
print(ethtool.get_coalesce(ifname))
