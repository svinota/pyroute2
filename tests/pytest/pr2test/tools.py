from pyroute2 import NetNS
from pyroute2 import IPRoute


def interface_exists(ifname, *argv, **kwarg):
    ret = 0
    ipr = None
    if argv and argv[0] is not None:
        ipr = NetNS(argv[0])
    else:
        ipr = IPRoute()

    spec = {}
    spec.update(kwarg)
    spec['ifname'] = ifname
    ret = list(ipr.link_lookup(**spec))
    ipr.close()

    return len(ret) == 1


def address_exists(ifname, *argv, **kwarg):
    ret = 0
    ipr = None
    if argv and argv[0] is not None:
        ipr = NetNS(argv[0])
    else:
        ipr = IPRoute()

    idx = list(ipr.link_lookup(ifname=ifname))[0]
    ret = list(ipr.addr('dump', index=idx, match=kwarg))
    ipr.close()

    return len(ret) == 1
