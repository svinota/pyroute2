from socket import AF_INET

from pr2modules.common import get_address_family
from pr2modules.netlink.rtnl.ndmsg import NUD_PERMANENT, ndmsg

from .common import Index, IPRouteFilter


class NeighbourFieldFilter(Index):
    def set_index(self, context, value):
        return {
            'ifindex': super(NeighbourFieldFilter, self).set_index(
                context, value
            )['index']
        }

    def _state(self, value):
        if isinstance(value, str):
            value = ndmsg.states_a2n(self['state'])
        return {'state': value}

    def set_nud(self, context, value):
        return self._state(value)

    def set_state(self, context, value):
        return self._state(value)


class NeighbourIPRouteFilter(IPRouteFilter):
    def set_dst(self, context, value):
        ret = {'dst': value}
        if 'family' not in context:
            ret['family'] = get_address_family(value)
        return ret

    def finalize(self, context):
        if self.command not in ('dump', 'get'):
            if 'state' not in context:
                context['state'] = NUD_PERMANENT
        if 'family' not in context:
            context['family'] = AF_INET
