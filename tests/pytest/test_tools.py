from pyroute2 import NetNS
from pyroute2 import IPRoute


def interface_exists(ifname, *argv, **kwarg):
    ret = 0
    ipr = None
    if argv:
        ipr = NetNS(argv[0])
    else:
        ipr = IPRoute()

    spec = {}
    spec.update(kwarg)
    spec['ifname'] = ifname
    ret = list(ipr.link_lookup(**spec))
    ipr.close()

    return len(ret) == 1
