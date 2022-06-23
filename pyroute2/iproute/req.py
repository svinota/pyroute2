import logging
from collections import OrderedDict
from socket import AF_INET, AF_INET6

from pyroute2.common import basestring
from pyroute2.netlink.rtnl.fibmsg import FR_ACT_NAMES
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


class IPRuleRequest(IPRequest):
    def fix_request(self):
        # now fix the rest
        if 'family' not in self:
            self['family'] = AF_INET
        if ('priority' not in self) and ('FRA_PRIORITY' not in self):
            self['priority'] = 32000
        if 'table' in self and 'action' not in self:
            self['action'] = 'to_tbl'
        for key in ('src_len', 'dst_len'):
            if self.get(key, None) is None and key[:3] in self:
                self[key] = {AF_INET6: 128, AF_INET: 32}[self['family']]

    def __setitem__(self, key, value):
        if key.startswith('ipdb_'):
            return

        if key in ('src', 'dst'):
            v = value.split('/')
            if len(v) == 2:
                value, self['%s_len' % key] = v[0], int(v[1])
        elif key == 'action' and isinstance(value, basestring):
            value = FR_ACT_NAMES.get(
                value, (FR_ACT_NAMES.get('FR_ACT_' + value.upper(), value))
            )

        self.set(key, value)


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
