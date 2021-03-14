from pyroute2 import IPRoute


def interface_exists(ifname):
    ret = 0
    with IPRoute() as ipr:
        ret = list(ipr.link_lookup(ifname=ifname))
    return len(ret) == 1
