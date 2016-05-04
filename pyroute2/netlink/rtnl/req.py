from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import AF_MPLS
from pyroute2.common import basestring
from pyroute2.netlink.rtnl import rt_type
from pyroute2.netlink.rtnl import rt_proto
from pyroute2.netlink.rtnl import rt_scope
from pyroute2.netlink.rtnl import encap_type
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh as nh_header


encap_types = {'mpls': 1,
               AF_MPLS: 1}


class IPRequest(dict):

    def __init__(self, obj=None):
        dict.__init__(self)
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


class IPRouteRequest(IPRequest):
    '''
    Utility class, that converts human-readable dictionary
    into RTNL route request.
    '''
    resolve = {'encap_type': encap_type,
               'type': rt_type,
               'proto': rt_proto,
               'scope': rt_scope}

    def encap_header(self, header):
        '''
        Encap header transform. Format samples:

            {'type': 'mpls',
             'labels': '200/300'}

            {'type': AF_MPLS,
             'labels': (200, 300)}

            {'type': 'mpls',
             'labels': 200}

            {'type': AF_MPLS,
             'labels': [{'bos': 0, 'label': 200, 'ttl': 16},
                        {'bos': 1, 'label': 300, 'ttl': 16}]}
        '''
        if isinstance(header['type'], int) or \
                (header['type'] in ('mpls', AF_MPLS)):
            ret = []
            override_bos = True
            labels = header['labels']
            if isinstance(labels, basestring):
                labels = labels.split('/')
            if not isinstance(labels, (tuple, list, set)):
                labels = (labels, )
            for label in labels:
                if isinstance(label, dict):
                    # dicts append intact
                    override_bos = False
                    ret.append(label)
                else:
                    # otherwise construct label dict
                    if isinstance(label, basestring):
                        label = int(label)
                    ret.append({'bos': 0, 'label': label})
            # the last label becomes bottom-of-stack
            if override_bos:
                ret[-1]['bos'] = 1
            return {'attrs': [['MPLS_IPTUNNEL_DST', ret]]}

    def mpls_rta(self, value):
        ret = []
        if not isinstance(value, (list, tuple, set)):
            value = (value, )
        for label in value:
            if isinstance(label, int):
                label = {'label': label,
                         'bos': 0}
            elif isinstance(label, basestring):
                label = {'label': int(label),
                         'bos': 0}
            elif not isinstance(label, dict):
                raise ValueError('wrong MPLS label')
            ret.append(label)
        if ret:
            ret[-1]['bos'] = 1
        return ret

    def __setitem__(self, key, value):
        # skip virtual IPDB fields
        if key.startswith('ipdb_'):
            return
        # fix family
        if isinstance(value, basestring) and value.find(':') >= 0:
            self['family'] = AF_INET6
        # work on the rest
        if key == 'family' and value == AF_MPLS:
            dict.__setitem__(self, 'family', value)
            dict.__setitem__(self, 'dst_len', 20)
            dict.__setitem__(self, 'table', 254)
            dict.__setitem__(self, 'type', 1)
        elif key == 'flags':
            if self['family'] == AF_MPLS:
                return
        elif key == 'dst':
            if isinstance(value, dict):
                dict.__setitem__(self, 'dst', value)
            elif isinstance(value, int):
                dict.__setitem__(self, 'dst', {'label': value,
                                               'bos': 1})
            elif value != 'default':
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
                if mask:
                    dict.__setitem__(self, 'dst_len', mask)
        elif key == 'newdst':
            dict.__setitem__(self, 'newdst', self.mpls_rta(value))
        elif key in self.resolve.keys():
            if isinstance(value, basestring):
                value = self.resolve[key][value]
            dict.__setitem__(self, key, value)
        elif key == 'encap':
            if isinstance(value, dict):
                # human-friendly form:
                #
                # 'encap': {'type': 'mpls',
                #           'labels': '200/300'}
                #
                # 'type' is mandatory
                if 'type' in value and 'labels' in value:
                    dict.__setitem__(self, 'encap_type',
                                     encap_types.get(value['type'],
                                                     value['type']))
                    dict.__setitem__(self, 'encap',
                                     self.encap_header(value))
                # assume it is a ready-to-use NLA
                elif 'attrs' in value:
                    dict.__setitem__(self, 'encap', value)
        elif key == 'via':
            # ignore empty RTA_VIA
            if isinstance(value, dict) and \
                    set(value.keys()) == set(('addr', 'family')) and \
                    value['family'] in (AF_INET, AF_INET6) and \
                    isinstance(value['addr'], basestring):
                        dict.__setitem__(self, 'via', value)
        elif key == 'metrics':
            if 'attrs' in value:
                ret = value
            else:
                ret = {'attrs': []}
                for name in value:
                    rtax = rtmsg.metrics.name2nla(name)
                    ret['attrs'].append([rtax, value[name]])
            if ret['attrs']:
                dict.__setitem__(self, 'metrics', ret)
        elif key == 'multipath':
            ret = []
            for v in value:
                if 'attrs' in v:
                    ret.append(v)
                    continue
                nh = {'attrs': []}
                nh_fields = [x[0] for x in nh_header.fields]
                for name in nh_fields:
                    nh[name] = v.get(name, 0)
                for name in v:
                    if name in nh_fields or v[name] is None:
                        continue
                    if name == 'encap' and isinstance(v[name], dict):
                        if v[name].get('type', None) is None or \
                                v[name].get('labels', None) is None:
                            continue
                        nh['attrs'].append(['RTA_ENCAP_TYPE',
                                            encap_types.get(v[name]['type'],
                                                            v[name]['type'])])
                        nh['attrs'].append(['RTA_ENCAP',
                                            self.encap_header(v[name])])
                    elif name == 'newdst':
                        nh['attrs'].append(['RTA_NEWDST',
                                            self.mpls_rta(v[name])])
                    else:
                        rta = rtmsg.name2nla(name)
                        nh['attrs'].append([rta, v[name]])
                ret.append(nh)
            if ret:
                dict.__setitem__(self, 'multipath', ret)
        else:
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


class IPBridgeRequest(IPRequest):

    def __setitem__(self, key, value):
        if key in ('vlan_info', 'mode', 'flags'):
            if 'IFLA_AF_SPEC' not in self:
                dict.__setitem__(self, 'IFLA_AF_SPEC', {'attrs': []})
            nla = ifinfmsg.af_spec_bridge.name2nla(key)
            self['IFLA_AF_SPEC']['attrs'].append([nla, value])
        else:
            dict.__setitem__(self, key, value)


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
            self['IFLA_LINKINFO'] = {'attrs': []}
            linkinfo = self['IFLA_LINKINFO']['attrs']
            linkinfo.append(['IFLA_INFO_KIND', value])
            if value in ('vlan', 'bond', 'tuntap', 'veth',
                         'vxlan', 'macvlan', 'macvtap', 'gre',
                         'gretap', 'ipvlan', 'bridge', 'vrf'):
                linkinfo.append(['IFLA_INFO_DATA', {'attrs': []}])
        elif key == 'vlan_id':
            nla = ['IFLA_VLAN_ID', value]
            # FIXME: we need to replace, not add
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'vlan')
        elif key == 'gid':
            nla = ['IFTUN_UID', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'tuntap')
        elif key == 'uid':
            nla = ['IFTUN_UID', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'tuntap')
        elif key == 'mode':
            nla = ['IFLA_IPVLAN_MODE', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'ipvlan')
            nla = ['IFTUN_MODE', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'tuntap')
            nla = ['IFLA_BOND_MODE', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'bond')
        elif key == 'stp_state':
            nla = ['IFLA_BRIDGE_STP_STATE', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'bridge')
        elif key == 'ifr':
            nla = ['IFTUN_IFR', value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'tuntap')
        elif key.startswith('macvtap'):
            nla = [ifinfmsg.name2nla(key), value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'macvtap')
        elif key.startswith('macvlan'):
            nla = [ifinfmsg.name2nla(key), value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'macvlan')
        elif key.startswith('gre'):
            nla = [ifinfmsg.name2nla(key), value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'gre' or
                           x.get('kind', None) == 'gretap')
        elif key.startswith('vxlan'):
            nla = [ifinfmsg.name2nla(key), value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'vxlan')
        elif key.startswith('vrf'):
            nla = [ifinfmsg.name2nla(key), value]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
                           lambda x: x.get('kind', None) == 'vrf')
        elif key == 'peer':
            if isinstance(value, dict):
                attrs = []
                for k, v in value.items():
                    attrs.append([ifinfmsg.name2nla(k), v])
            else:
                attrs = [['IFLA_IFNAME', value], ]
            nla = ['VETH_INFO_PEER', {'attrs': attrs}]
            self.defer_nla(nla, ('IFLA_LINKINFO', 'IFLA_INFO_DATA'),
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
                if step in pwd:
                    pwd = pwd[step]
                else:
                    pwd = [x[1] for x in pwd['attrs']
                           if x[0] == step][0]['attrs']
            pwd.append(nla)

    def defer_nla(self, nla, path, predicate):
        self.deferred.append((nla, path, predicate))
        self.flush_deferred()
