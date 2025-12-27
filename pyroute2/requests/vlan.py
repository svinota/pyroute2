from pyroute2.config import AF_BRIDGE
from pyroute2.netlink.rtnl.br_vlan import br_vlan_base, br_vlan_msg
from pyroute2.netlink.rtnl.ifinfmsg import BRIDGE_VLAN_INFO_ONLY_OPTS

from .common import Index, IPRouteFilter, NLAKeyTransform


class VlanFieldFilter(Index, NLAKeyTransform):
    _nla_prefix = br_vlan_base.prefix


class VlanIPRouteFilter(IPRouteFilter):

    def finalize(self, context):
        if 'family' not in context:
            context['family'] = AF_BRIDGE

        if self.command == 'set':
            instruction = None
            entry = br_vlan_msg.entry()

            for k, v in context.items():
                if entry.valid_nla(entry.name2nla(k)):
                    instruction = (entry.name2nla(k), v)
                    break
            else:
                raise ValueError('no valid vlan DB instruction is given')

            context['BRIDGE_VLANDB_ENTRY'] = {
                'attrs': [
                    (
                        'BRIDGE_VLANDB_ENTRY_INFO',
                        {
                            'flags': BRIDGE_VLAN_INFO_ONLY_OPTS,
                            'vid': context.pop('vid'),
                        },
                    ),
                    instruction,
                ]
            }
