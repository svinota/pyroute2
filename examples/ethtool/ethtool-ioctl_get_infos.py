import sys
from pyroute2.ethtool.ioctl import IoctlEthtool
from pyroute2.ethtool.ioctl import NotSupportedError

if len(sys.argv) != 2:
    raise Exception("USAGE: {0} IFNAME".format(sys.argv[0]))


dev = IoctlEthtool(sys.argv[1])
print("=== Device cmd: ===")
try:
    for name, value in dev.get_cmd().items():
        print("\t{}: {}".format(name, value))
except NotSupportedError:
    print("Not supported by driver.\n")
print("")

print("=== Device feature: ===")
for name, value, not_fixed, _, _ in dev.get_features():
    value = "on" if value else "off"
    if not not_fixed:
        # I love double negations
        value += " [fixed]"
        print("\t{}: {}".format(name, value))

print("\n=== Device coalesce: ===")
for name, value in dev.get_coalesce().items():
    print("\t{}: {}".format(name, value))
