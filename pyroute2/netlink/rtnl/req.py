from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import AF_MPLS
from pyroute2.common import basestring
from pyroute2.netlink.rtnl import rt_type
from pyroute2.netlink.rtnl import rt_proto
from pyroute2.netlink.rtnl import rt_scope
from pyroute2.netlink.rtnl import encap_type
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifinfmsg import protinfo_bridge
from pyroute2.netlink.rtnl.ifinfmsg.plugins.vlan import flags as vlan_flags
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh as nh_header
from pyroute2.netlink.rtnl.fibmsg import FR_ACT_NAMES


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


class IPRuleRequest(IPRequest):

    def update(self, obj):
        super(IPRuleRequest, self).update(obj)
        # now fix the rest
        if 'family' not in self:
            self['family'] = AF_INET
        if 'priority' not in self:
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
            value = (FR_ACT_NAMES
                     .get(value, (FR_ACT_NAMES
                                  .get('FR_ACT_' + value.upper(), value))))

        dict.__setitem__(self, key, value)


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
        elif key == 'flags' and self.get('family', None) == AF_MPLS:
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
        if key in ('vlan_info', 'mode', 'vlan_flags'):
            if 'IFLA_AF_SPEC' not in self:
                dict.__setitem__(self, 'IFLA_AF_SPEC', {'attrs': []})
            nla = ifinfmsg.af_spec_bridge.name2nla(key)
            self['IFLA_AF_SPEC']['attrs'].append([nla, value])
        else:
            dict.__setitem__(self, key, value)


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


class IPLinkRequest(IPRequest):
    '''
    Utility class, that converts human-readable dictionary
    into RTNL link request.
    '''
    blacklist = ['carrier',
                 'carrier_changes']

    # get common ifinfmsg NLAs
    common = []
    for (key, _) in ifinfmsg.nla_map:
        common.append(key)
        common.append(key[len(ifinfmsg.prefix):].lower())
    common.append('family')
    common.append('ifi_type')
    common.append('index')
    common.append('flags')
    common.append('change')

    def __init__(self, *argv, **kwarg):
        self.deferred = []
        self.kind = None
        self.specific = {}
        self.linkinfo = None
        self._info_data = None
        IPRequest.__init__(self, *argv, **kwarg)
        if 'index' not in self:
            self['index'] = 0

    @property
    def info_data(self):
        if self._info_data is None:
            info_data = ('IFLA_INFO_DATA', {'attrs': []})
            self._info_data = info_data[1]['attrs']
            self.linkinfo.append(info_data)
        return self._info_data

    def flush_deferred(self):
        # create IFLA_LINKINFO
        linkinfo = {'attrs': []}
        self.linkinfo = linkinfo['attrs']
        dict.__setitem__(self, 'IFLA_LINKINFO', linkinfo)
        self.linkinfo.append(['IFLA_INFO_KIND', self.kind])
        # load specific NLA names
        cls = ifinfmsg.ifinfo.data_map.get(self.kind, None)
        if cls is not None:
            prefix = cls.prefix or 'IFLA_'
            for nla, _ in cls.nla_map:
                self.specific[nla] = nla
                self.specific[nla[len(prefix):].lower()] = nla

        # flush deferred NLAs
        for (key, value) in self.deferred:
            if not self.set_specific(key, value):
                dict.__setitem__(self, key, value)

        self.deferred = []

    def set_specific(self, key, value):
        # FIXME: vlan hack
        if self.kind == 'vlan' and key == 'vlan_flags':
            if isinstance(value, (list, tuple)):
                if len(value) == 2 and \
                        all((isinstance(x, int) for x in value)):
                    value = {'flags': value[0],
                             'mask': value[1]}
                else:
                    ret = 0
                    for x in value:
                        ret |= vlan_flags.get(x, 1)
                    value = {'flags': ret,
                             'mask': ret}
            elif isinstance(value, int):
                value = {'flags': value,
                         'mask': value}
            elif isinstance(value, basestring):
                value = vlan_flags.get(value, 1)
                value = {'flags': value,
                         'mask': value}
            elif not isinstance(value, dict):
                raise ValueError()
        # the kind is known: lookup the NLA
        if key in self.specific:
            self.info_data.append((self.specific[key], value))
            return True
        elif key == 'peer' and self.kind == 'veth':
            # FIXME: veth hack
            if isinstance(value, dict):
                attrs = []
                for k, v in value.items():
                    attrs.append([ifinfmsg.name2nla(k), v])
            else:
                attrs = [['IFLA_IFNAME', value], ]
            nla = ['VETH_INFO_PEER', {'attrs': attrs}]
            self.info_data.append(nla)
            return True
        elif key == 'mode':
            # FIXME: ipvlan / tuntap / bond hack
            if self.kind == 'ipvlan':
                nla = ['IFLA_IPVLAN_MODE', value]
            elif self.kind == 'tuntap':
                nla = ['IFTUN_MODE', value]
            elif self.kind == 'bond':
                nla = ['IFLA_BOND_MODE', value]
            self.info_data.append(nla)
            return True

        return False

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

        if key == 'kind' and not self.kind:
            self.kind = value
            self.flush_deferred()
        elif self.kind is None:
            if key in self.common:
                dict.__setitem__(self, key, value)
            else:
                self.deferred.append((key, value))
        else:
            if not self.set_specific(key, value):
                dict.__setitem__(self, key, value)
