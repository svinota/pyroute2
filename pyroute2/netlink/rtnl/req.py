from socket import AF_INET6
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.brmsg import brmsg
from pyroute2.netlink.rtnl.bomsg import bomsg


class IPRequest(dict):

    def __init__(self, obj=None):
        dict.__init__(self)
        if obj is not None:
            self.update(obj)

    def update(self, obj):
        for key in obj:
            if obj[key] is not None:
                self[key] = obj[key]


class IPRouteRequest(IPRequest):
    '''
    Utility class, that converts human-readable dictionary
    into RTNL route request.
    '''

    def __setitem__(self, key, value):
        # fix family
        if isinstance(value, basestring) and value.find(':') >= 0:
            self['family'] = AF_INET6
        # work on the rest
        if (key == 'dst') and (value != 'default'):
            value = value.split('/')
            if len(value) == 1:
                dst = value[0]
                mask = 0
            elif len(value) == 2:
                dst = value[0]
                mask = int(value[1])
            else:
                raise ValueError('wrong destination')
            dict.__setitem__(self, 'dst', dst)
            dict.__setitem__(self, 'dst_len', mask)
        elif key != 'dst':
            dict.__setitem__(self, key, value)


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
            self['commands']['attrs'].\
                append([self.msg.name2nla(key), value])
        else:
            dict.__setitem__(self, key, value)


class BridgeRequest(CBRequest):
    commands = [brmsg.nla2name(i[0]) for i in brmsg.commands.nla_map]
    msg = brmsg


class BondRequest(CBRequest):
    commands = [bomsg.nla2name(i[0]) for i in bomsg.commands.nla_map]
    msg = bomsg


class IPLinkRequest(IPRequest):
    '''
    Utility class, that converts human-readable dictionary
    into RTNL link request.
    '''
    blacklist = ['carrier',
                 'carrier_changes']

    def __init__(self, *argv, **kwarg):
        self.deferred = []
        IPRequest.__init__(self, *argv, **kwarg)
        if 'index' not in self:
            self['index'] = 0

    def __setitem__(self, key, value):
        # ignore blacklisted attributes
        if key in self.blacklist:
            return

        # there must be no "None" values in the request
        if value is None:
            return

        # all the values must be in ascii
        try:
            if isinstance(value, unicode):
                value = value.encode('ascii')
        except NameError:
            pass

        # set up specific keys
        if key == 'kind':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_KIND', value]
            # FIXME: we need to replace, not add
            self['IFLA_LINKINFO']['attrs'].append(nla)
        elif key == 'vlan_id':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_DATA', {'attrs': [['IFLA_VLAN_ID', value]]}]
            # FIXME: we need to replace, not add
            self['IFLA_LINKINFO']['attrs'].append(nla)
        elif key == 'bond_mode':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_DATA', {'attrs': [['IFLA_BOND_MODE', value]]}]
            self['IFLA_LINKINFO']['attrs'].append(nla)
        elif key == 'peer':
            nla = ['IFLA_INFO_DATA',
                   {'attrs': [['VETH_INFO_PEER',
                               {'attrs': [['IFLA_IFNAME', value]]}]]}]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'attrs'),
                           lambda x: x.get('kind', None) == 'veth')
        dict.__setitem__(self, key, value)
        if self.deferred:
            self.flush_deferred()

    def flush_deferred(self):
        deferred = []
        for nla, path, predicate in self.deferred:
            if predicate(self):
                self.append_nla(nla, path)
            else:
                deferred.append((nla, path, predicate))
        self.deferred = deferred

    def append_nla(self, nla, path):
            pwd = self
            for step in path:
                pwd = pwd[step]
            pwd.append(nla)

    def defer_nla(self, nla, path, predicate):
        self.deferred.append((nla, path, predicate))
        self.flush_deferred()
