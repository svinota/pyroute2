import logging
from collections import OrderedDict
from socket import AF_INET, AF_INET6

from pr2modules.common import basestring
from pr2modules.netlink.rtnl.fibmsg import FR_ACT_NAMES
from pr2modules.netlink.rtnl.ifinfmsg import (
    IFF_NOARP,
    ifinfmsg,
    protinfo_bridge,
)
from pr2modules.netlink.rtnl.ifinfmsg.plugins.vlan import flags as vlan_flags

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


class IPLinkRequest(IPRequest):
    '''
    Utility class, that converts human-readable dictionary
    into RTNL link request.
    '''

    blacklist = ['carrier', 'carrier_changes', 'info_slave_kind']

    # get common ifinfmsg NLAs
    common = []
    for (key, _) in ifinfmsg.nla_map:
        common.append(key)
        common.append(key[len(ifinfmsg.prefix) :].lower())
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
        self._info_slave_data = None
        for key in ('index', 'change', 'flags'):
            self.set(key, 0)
        IPRequest.__init__(self, *argv, **kwarg)

    @property
    def info_data(self):
        if self._info_data is None:
            info_data = ('IFLA_INFO_DATA', {'attrs': []})
            self._info_data = info_data[1]['attrs']
            self.linkinfo.append(info_data)
        return self._info_data

    @property
    def info_slave_data(self):
        if self._info_slave_data is None:
            info_slave_data = ('IFLA_INFO_SLAVE_DATA', {'attrs': []})
            self._info_slave_data = info_slave_data[1]['attrs']
            self.linkinfo.append(info_slave_data)
        return self._info_slave_data

    def flush_deferred(self):
        # create IFLA_LINKINFO
        linkinfo = {'attrs': []}
        self.linkinfo = linkinfo['attrs']
        self.set('IFLA_LINKINFO', linkinfo)
        self.linkinfo.append(['IFLA_INFO_KIND', self.kind])
        # load specific NLA names
        cls = ifinfmsg.ifinfo.data_map.get(self.kind, None)
        if cls is not None:
            prefix = cls.prefix or 'IFLA_'
            for nla, _ in cls.nla_map:
                self.specific[nla] = nla
                self.specific[nla[len(prefix) :].lower()] = nla

        # flush deferred NLAs
        for (key, value) in self.deferred:
            if not self.set_specific(key, value):
                super(IPLinkRequest, self).__setitem__(key, value)

        self.deferred = []

    def set_vf(self, spec):
        vflist = []
        if not isinstance(spec, (list, tuple)):
            spec = (spec,)
        for vf in spec:
            vfcfg = []
            # pop VF index
            vfid = vf.pop('vf')  # mandatory
            # pop VLAN spec
            vlan = vf.pop('vlan', None)  # optional
            if isinstance(vlan, int):
                vfcfg.append(('IFLA_VF_VLAN', {'vf': vfid, 'vlan': vlan}))
            elif isinstance(vlan, dict):
                vlan['vf'] = vfid
                vfcfg.append(('IFLA_VF_VLAN', vlan))
            elif isinstance(vlan, (list, tuple)):
                vlist = []
                for vspec in vlan:
                    vspec['vf'] = vfid
                    vlist.append(('IFLA_VF_VLAN_INFO', vspec))
                vfcfg.append(('IFLA_VF_VLAN_LIST', {'attrs': vlist}))
            # pop rate spec
            rate = vf.pop('rate', None)  # optional
            if rate is not None:
                rate['vf'] = vfid
                vfcfg.append(('IFLA_VF_RATE', rate))
            # create simple VF attrs
            for attr in vf:
                vfcfg.append(
                    (
                        ifinfmsg.vflist.vfinfo.name2nla(attr),
                        {'vf': vfid, attr: vf[attr]},
                    )
                )
            vflist.append(('IFLA_VF_INFO', {'attrs': vfcfg}))
        self.set('IFLA_VFINFO_LIST', {'attrs': vflist})

    def set_specific(self, key, value):
        # FIXME: vlan hack
        if self.kind == 'vlan' and key == 'vlan_flags':
            if isinstance(value, (list, tuple)):
                if len(value) == 2 and all(
                    (isinstance(x, int) for x in value)
                ):
                    value = {'flags': value[0], 'mask': value[1]}
                else:
                    ret = 0
                    for x in value:
                        ret |= vlan_flags.get(x, 1)
                    value = {'flags': ret, 'mask': ret}
            elif isinstance(value, int):
                value = {'flags': value, 'mask': value}
            elif isinstance(value, basestring):
                value = vlan_flags.get(value, 1)
                value = {'flags': value, 'mask': value}
            elif not isinstance(value, dict):
                raise ValueError()
        # the kind is known: lookup the NLA
        if key in self.specific:
            # FIXME: slave hack
            if self.kind.endswith('_slave'):
                self.info_slave_data.append((self.specific[key], value))
            else:
                self.info_data.append((self.specific[key], value))
            return True
        elif key == 'peer' and self.kind == 'veth':
            # FIXME: veth hack
            if isinstance(value, dict):
                attrs = []
                for k, v in value.items():
                    attrs.append([ifinfmsg.name2nla(k), v])
            else:
                attrs = [['IFLA_IFNAME', value]]
            nla = ['VETH_INFO_PEER', {'attrs': attrs}]
            self.info_data.append(nla)
            return True
        elif key == 'mode':
            # FIXME: ipvlan / tuntap / bond hack
            if self.kind == 'tuntap':
                nla = ['IFTUN_MODE', value]
            else:
                nla = ['IFLA_%s_MODE' % self.kind.upper(), value]
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

        if key in ('kind', 'info_kind') and not self.kind:
            self.kind = value
            self.flush_deferred()
        elif key == 'vf':  # SR-IOV virtual function setup
            self.set_vf(value)
        elif key == 'xdp_fd':
            attrs = [('IFLA_XDP_FD', value)]
            self.set('xdp', {'attrs': attrs})
        elif key == 'state':
            if value == 'up':
                self.set('flags', self['flags'] | 1)
            self.set('change', self['change'] | 1)
        elif key == 'mask':
            self.set('change', value)
        elif key == 'arp':
            if not value:
                self.set('flags', self['flags'] | IFF_NOARP)
            self.set('change', self['change'] | IFF_NOARP)
        elif key == 'noarp':
            if value:
                self.set('flags', self['flags'] | IFF_NOARP)
            self.set('change', self['change'] | IFF_NOARP)
        elif key == 'altname':
            if self.command in ('property_add', 'property_del'):
                if not isinstance(value, (list, tuple, set)):
                    value = [value]
                self.set(
                    'IFLA_PROP_LIST',
                    {
                        'attrs': [
                            ('IFLA_ALT_IFNAME', alt_ifname)
                            for alt_ifname in value
                        ]
                    },
                )
            else:
                self.set('IFLA_ALT_IFNAME', value)
        elif self.kind is None:
            if key in self.common:
                self.set(key, value)
            else:
                self.deferred.append((key, value))
        else:
            if not self.set_specific(key, value):
                self.set(key, value)
