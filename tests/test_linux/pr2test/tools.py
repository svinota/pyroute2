from pr2modules.iproute.linux import IPRoute
from pr2modules.nslink.nslink import NetNS


def interface_exists(netns=None, *argv, **kwarg):
    ret = 0
    ipr = None

    if netns is None:
        ipr = IPRoute()
    else:
        ipr = NetNS(netns)

    spec = {}
    spec.update(kwarg)
    ret = list(ipr.link_lookup(*argv, **spec))
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
        links = list(ipr.link_lookup(ifname=kwarg['ifname']))
        if links:
            nkw['index'] = links[0]
            nkw.pop('ifname')
        else:
            ipr.close()
            return 0

    ret = list(ipr.addr('dump', match=nkw))
    ipr.close()

    return len(ret) == 1


def rtnl_object_exists(api, netns, record_filter):
    ret = 0
    ipr = None

    if netns is None:
        ipr = IPRoute()
    else:
        ipr = NetNS(netns)

    ret = list(getattr(ipr, api)('dump', **record_filter))
    ipr.close()
    return len(ret) >= 1


def neighbour_exists(netns=None, **kwarg):
    return rtnl_object_exists('neigh', netns, kwarg)


def route_exists(netns=None, **kwarg):
    return rtnl_object_exists('route', netns, kwarg)


def rule_exists(netns=None, **kwarg):
    return rtnl_object_exists('rule', netns, kwarg)


def fdb_record_exists(netns=None, **kwarg):
    return rtnl_object_exists('fdb', netns, kwarg)


def qdisc_exists(netns=None, kind=None, **kwarg):
    if netns is None:
        ipr = IPRoute()
    else:
        ipr = NetNS(netns)
    opts = {}
    with ipr:
        if 'ifname' in kwarg:
            opts['index'] = ipr.link_lookup(ifname=kwarg.pop('ifname'))[0]
        ret = list(ipr.get_qdiscs(**opts))
        if kind is not None:
            ret = [x for x in ret if x.get_attr('TCA_KIND') == kind]
        if kwarg:
            pre = ret
            ret = []
            for qdisc in pre:
                options = qdisc.get_attr('TCA_OPTIONS')
                if 'attrs' in options:
                    options = dict(options['attrs'])
                for opt in kwarg:
                    if kwarg[opt] not in (
                        options.get(opt),
                        options.get(qdisc.name2nla(opt)),
                    ):
                        break
                else:
                    ret.append(qdisc)
        return ret
