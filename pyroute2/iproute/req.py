import logging
from collections import OrderedDict

from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg, protinfo_bridge

log = logging.getLogger(__name__)


class IPRequest(OrderedDict):
    def __init__(self, obj=None, command=None):
        super(IPRequest, self).__init__()
        self.command = command
        if obj is not None:
            self.update(obj)

    def update(self, obj):
        if obj.get('family', None):
            self['family'] = obj['family']
        for key in obj:
            if key == 'family':
                continue
            v = obj[key]
            if isinstance(v, dict):
                self[key] = dict((x for x in v.items() if x[1] is not None))
            elif v is not None:
                self[key] = v
        self.fix_request()

    def fix_request(self):
        pass

    def set(self, key, value):
        return super(IPRequest, self).__setitem__(key, value)

    def sync_cacheinfo(self):
        pass


class CBRequest(IPRequest):
    '''
    FIXME
    '''

    commands = None
    msg = None

    def __init__(self, *argv, **kwarg):
        self['commands'] = {'attrs': []}

    def __setitem__(self, key, value):
        if value is None:
            return
        if key in self.commands:
            self['commands']['attrs'].append([self.msg.name2nla(key), value])
        else:
            self.set(key, value)


class IPBridgeRequest(IPRequest):
    def __setitem__(self, key, value):
        if key in ('vlan_info', 'mode', 'vlan_flags'):
            if 'IFLA_AF_SPEC' not in self:
                (
                    super(IPBridgeRequest, self).__setitem__(
                        'IFLA_AF_SPEC', {'attrs': []}
                    )
                )
            nla = ifinfmsg.af_spec_bridge.name2nla(key)
            self['IFLA_AF_SPEC']['attrs'].append([nla, value])
        else:
            self.set(key, value)


class IPBrPortRequest(dict):
    def __init__(self, obj=None):
        dict.__init__(self)
        dict.__setitem__(self, 'attrs', [])
        self.allowed = [x[0] for x in protinfo_bridge.nla_map]
        if obj is not None:
            self.update(obj)

    def update(self, obj):
        for key in obj:
            self[key] = obj[key]

    def __setitem__(self, key, value):
        key = protinfo_bridge.name2nla(key)
        if key in self.allowed:
            self['attrs'].append((key, value))
