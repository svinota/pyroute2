from pyroute2 import NetNS
from pyroute2 import IPRoute


def interface_exists(netns=None, **kwarg):
    ret = 0
    ipr = None

    if netns is None:
        ipr = IPRoute()
    else:
        ipr = NetNS(netns)

    spec = {}
    spec.update(kwarg)
    ret = list(ipr.link_lookup(**spec))
    ipr.close()

    return len(ret) >= 1


def address_exists(netns=None, **kwarg):
    ret = 0
    ipr = None

    if netns is None:
        ipr = IPRoute()
    else:
        ipr = NetNS(netns)

    if 'match' in kwarg:
        nkw = kwarg['match']
    else:
        nkw = dict(kwarg)
        for key in ('address', 'local'):
            if key in nkw:
                nkw[key] = nkw[key].split('/')[0]

    if 'ifname' in kwarg:
        nkw['index'] = list(ipr.link_lookup(ifname=kwarg['ifname']))[0]
        nkw.pop('ifname')

    ret = list(ipr.addr('dump', match=nkw))
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
