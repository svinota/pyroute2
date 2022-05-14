from collections import OrderedDict

from pr2modules.netlink.rtnl import rt_proto
from pr2modules.netlink.rtnl.rtmsg import LWTUNNEL_ENCAP_MPLS, rtmsg

from .common import IPTargets


class Target(OrderedDict):
    def __init__(self, prime=None):
        super(OrderedDict, self).__init__()
        if prime is None:
            prime = {}
        elif isinstance(prime, int):
            prime = {'label': prime}
        elif isinstance(prime, dict):
            pass
        else:
            raise TypeError()
        self['label'] = prime.get('label', 16)
        self['tc'] = prime.get('tc', 0)
        self['bos'] = prime.get('bos', 1)
        self['ttl'] = prime.get('ttl', 0)

    def __eq__(self, right):
        return (
            isinstance(right, (dict, Target))
            and self['label'] == right.get('label', 16)
            and self['tc'] == right.get('tc', 0)
            and self['bos'] == right.get('bos', 1)
            and self['ttl'] == right.get('ttl', 0)
        )

    def __repr__(self):
        return repr(dict(self))


class RouteFieldFilter(IPTargets):
    def flags(self, context, value):
        if isinstance(value, (list, tuple, str)):
            return {'flags': rtmsg.names2flags(value)}
        return {'flags': value}

    def _index(self, key, context, value):
        if isinstance(value, (list, tuple)):
            value = value[0]
        return {key: value}

    def oif(self, context, value):
        return self._index('oif', context, value)

    def iif(self, context, value):
        return self._index('iif', context, value)

    def scope(self, context, value):
        if isinstance(value, str):
            return {'scope': rtmsg.name2scope(value)}
        return {'scope': value}

    def proto(self, context, value):
        if isinstance(value, str):
            return {'proto': rt_proto[value]}
        return {'proto': value}

    def encap(self, context, value):
        if isinstance(value, dict) and value.get('type') == 'mpls':
            na = []
            target = None
            value = value.get('labels', [])
            if isinstance(value, (dict, int)):
                value = [value]
            for label in value:
                target = Target(label)
                target['bos'] = 0
                na.append(target)
            target['bos'] = 1
            return {'encap_type': LWTUNNEL_ENCAP_MPLS, 'encap': na}
        return {'encap': value}
