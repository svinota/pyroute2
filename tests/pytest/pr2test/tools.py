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

    if 'match' in kwarg:
        nkw = kwarg['match']
    else:
        nkw = dict(kwarg)
        for key in ('address', 'local'):
            if key in nkw:
                nkw[key] = nkw[key].split('/')[0]

    idx = list(ipr.link_lookup(ifname=ifname))[0]
    ret = list(ipr.addr('dump', index=idx, match=nkw))
    ipr.close()

    return len(ret) == 1


def route_exists(netns=None, **kwarg):
    ret = 0
    ipr = None
    if netns is not None:
        ipr = NetNS(netns)
    else:
        ipr = IPRoute()

    ret = list(ipr.route('dump', **kwarg))
    ipr.close()
    return len(ret) >= 1
