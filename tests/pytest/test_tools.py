from pyroute2 import IPRoute


def interface_exists(ifname, **kwarg):
    ret = 0
    with IPRoute() as ipr:
        spec = {}
        spec.update(kwarg)
        spec['ifname'] = ifname
        ret = list(ipr.link_lookup(**spec))
    return len(ret) == 1
