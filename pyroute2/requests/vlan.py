from pyroute2.config import AF_BRIDGE
from pyroute2.netlink.rtnl.br_vlan import br_vlan_base

from .common import Index, IPRouteFilter, NLAKeyTransform


class VlanFieldFilter(Index, NLAKeyTransform):
    _nla_prefix = br_vlan_base.prefix


class VlanIPRouteFilter(IPRouteFilter):

    def finalize(self, context):
        if 'family' not in context:
            context['family'] = AF_BRIDGE
