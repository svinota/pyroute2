from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg, protinfo_bridge

from .common import Index, IPRouteFilter, NLAKeyTransform


class BridgeFieldFilter(Index, NLAKeyTransform):

    _nla_prefix = ifinfmsg.prefix


class BridgeIPRouteFilter(IPRouteFilter):
    def finalize(self, context):
        if self.command != 'dump':
            for key in ('vlan_info', 'mode', 'vlan_flags'):
                if key in context:
                    if 'IFLA_AF_SPEC' not in context:
                        context['IFLA_AF_SPEC'] = {'attrs': []}
                    nla = ifinfmsg.af_spec_bridge.name2nla(key)
                    value = context[key]
                    try:
                        del context[key]
                    except KeyError:
                        pass
                    context['IFLA_AF_SPEC']['attrs'].append([nla, value])


class BridgePortFieldFilter(IPRouteFilter):

    _nla_prefix = ifinfmsg.prefix
    _allowed = [x[0] for x in protinfo_bridge.nla_map]
    _allowed.append('attrs')

    def finalize(self, context):
        keys = tuple(context.keys())
        context['attrs'] = []
        for key in keys:
            context['attrs'].append(
                (protinfo_bridge.name2nla(key), context[key])
            )
