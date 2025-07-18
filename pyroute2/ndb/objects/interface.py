'''

.. testsetup::

    from pyroute2 import NDB
    from pyroute2 import config

    config.mock_netlink = True


.. testsetup:: preset_1

    from pyroute2 import NDB
    from pyroute2 import config

    config.mock_netlink = True
    ndb = NDB(
        sources=[
            {'target': 'localhost', 'kind': 'local'},
            {'target': 'worker1.sample.com', 'kind': 'local'},
            {'target': 'worker2.sample.com', 'kind': 'local'},
        ]
    )

.. testsetup:: preset_br0_1

    from pyroute2 import NDB
    from pyroute2 import config
    config.mock_netlink = True
    ndb = NDB()
    ndb.interfaces.create(ifname='eth1', kind='dummy').commit()
    ndb.interfaces.create(ifname='br0', kind='bridge').commit()
    ndb.interfaces.create(ifname='bond0', kind='bond').commit()

.. testsetup:: preset_br0_2

    from pyroute2 import NDB
    from pyroute2 import config
    config.mock_netlink = True
    ndb = NDB()
    ndb.interfaces.create(ifname='br0', kind='bridge').commit()
    ndb.interfaces['br0'].add_port('eth0').commit()


List interfaces
===============

List interface keys:

.. testcode::

    with NDB(log='on') as ndb:
        for key in ndb.interfaces:
            print(key)


.. testoutput::
    :hide:

    ('localhost', 0, 0, 772, 1, 1, 0, '00:00:00:00:00:00', \
'00:00:00:00:00:00', 'lo', 65536, None, 'noqueue', None, 1000, 'UNKNOWN', 0, \
None, None, None, 0, None, 0, 1, 1, 1, 0, None, None, 0, 65535, 65536, None, \
None, None, 0, 0, None, None, None, None, None, None, 65536, None, None, \
'up', None, None, None, None, None, None, None, None, '[]')
    ('localhost', 0, 0, 772, 2, 1, 0, '52:54:00:72:58:b2', \
'ff:ff:ff:ff:ff:ff', 'eth0', 1500, None, 'fq_codel', None, 1000, 'UNKNOWN', \
0, None, None, None, 0, None, 0, 1, 1, 1, 0, None, None, 0, 65535, 65536, \
None, None, None, 0, 0, None, None, None, None, None, None, 65536, None, \
None, 'up', None, None, None, None, None, None, None, None, '[]')

NDB views support some dict methods: `items()`, `values()`, `keys()`:

.. testcode::

    with NDB(log='on') as ndb:
        for key, nic in ndb.interfaces.items():
            nic.set('state', 'up')
            nic.commit()

Get interface objects
=====================

The keys may be used as selectors to get interface objects:

.. testcode::

    with NDB() as ndb:
        for key in ndb.interfaces:
            print(ndb.interfaces[key])

.. testoutput::
    :hide:
    :options: +ELLIPSIS

    ...

Also possible selector formats are `dict()` and simple string. The latter
means the interface name:

.. testcode:: preset_1

    eth0 = ndb.interfaces['eth0']

Dict selectors are necessary to get interfaces by other properties:


.. testcode:: preset_1

    wrk1_eth0 = ndb.interfaces[{'target': 'worker1.sample.com',
                                'ifname': 'eth0'}]

    wrk2_eth0 = ndb.interfaces[{'target': 'worker2.sample.com',
                                'address': '52:54:00:72:58:b2'}]

Change nic properties
=====================

Changing MTU and MAC address:

.. testcode:: preset_1

    with ndb.interfaces['eth0'] as eth0:
        eth0['mtu'] = 1248
        eth0['address'] = '00:11:22:33:44:55'
    # --> <-- eth0.commit() is called by the context manager

One can change a property either using the assignment statement, or
using the `.set()` routine:

.. testcode:: preset_1

    # same code
    with ndb.interfaces['eth0'] as eth0:
        eth0.set('mtu', 1248)
        eth0.set('address', '00:11:22:33:44:55')


Create virtual interfaces
=========================

Create a bridge and add a port, `eth0`:

.. testcode:: preset_1

    with ndb.interfaces.create(ifname='br0', kind='bridge') as br0:
        br0.add_port('eth0')

Bridge and bond ports
=====================

Add bridge and bond ports one can use specific API:

.. code::

    with ndb.interfaces['br0'] as br0:
        br0.add_port('eth0')
        br0.add_port('eth1')
        br0.set('br_max_age', 1024)
        br0.set('br_forward_delay', 1500)

    with ndb.interfaces['bond0'] as bond0:
        bond0.add_port('eth0')
        bond0.add_port('eth1')

To remove a port:

.. code::

    with ndb.interfaces['br0'] as br0:
        br0.del_port('eth0')

Or by setting the master property on a port, in the same
way as with `IPRoute`:

.. code::

    index = ndb.interfaces['br0']['index']

    # add a port to a bridge
    with ndb.interfaces['eth0'] as eth0:
        eth0.set('master', index)

    # remove a port from a bridge
    with ndb.interfaces['eth0'] as eth0:
        eth0.set('master', 0)
'''

import errno
import json
import os
import traceback

from pyroute2.common import basestring
from pyroute2.config import AF_BRIDGE
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.p2pmsg import p2pmsg
from pyroute2.requests.link import LinkFieldFilter

from ..objects import AsyncObject, RTNL_Object
from ..sync_api import Flags, SyncView


async def load_ifinfmsg(schema, sources, target, event):
    #
    # link goes down: flush all related routes
    #
    if not event['flags'] & 1:
        schema.execute(
            '''
               DELETE FROM routes WHERE
               f_target = ? AND
               f_RTA_OIF = ? OR f_RTA_IIF = ?
            ''',
            (target, event['index'], event['index']),
        )
    #
    # ignore wireless updates
    #
    if event.get_attr('IFLA_WIRELESS'):
        return
    #
    # IFLA_PROP_LIST, IFLA_ALT_IFNAME
    #
    prop_list = event.get('IFLA_PROP_LIST')
    event['alt_ifname_list'] = []
    if prop_list is not None:
        for ifname in prop_list.altnames():
            event['alt_ifname_list'].append(ifname)

    #
    # AF_BRIDGE events
    #
    if event['family'] == AF_BRIDGE:
        #
        await schema.load_netlink('af_bridge_ifs', sources, target, event)
        try:
            vlans = event.get_attr('IFLA_AF_SPEC').get_attrs(
                'IFLA_BRIDGE_VLAN_INFO'
            )
        except AttributeError:
            # AttributeError: 'NoneType' object has no attribute 'get_attrs'
            # -- vlan filters not supported
            return

        # flush the old vlans info
        schema.execute(
            '''
               DELETE FROM af_bridge_vlans
               WHERE
                   f_target = ?
                   AND f_index = ?
            ''',
            (target, event['index']),
        )
        for v in vlans:
            v['index'] = event['index']
            v['header'] = {'type': event['header']['type']}
            await schema.load_netlink('af_bridge_vlans', sources, target, v)

        return

    await schema.load_netlink('interfaces', sources, target, event)
    #
    # load ifinfo, if exists
    #
    if not event['header'].get('type', 0) % 2:
        linkinfo = event.get_attr('IFLA_LINKINFO')
        if linkinfo is not None:
            iftype = linkinfo.get_attr('IFLA_INFO_KIND')
            table = f'ifinfo_{iftype}'
            if iftype == 'gre':
                ifdata = linkinfo.get_attr('IFLA_INFO_DATA')
                local = ifdata.get_attr('IFLA_GRE_LOCAL')
                remote = ifdata.get_attr('IFLA_GRE_REMOTE')
                p2p = p2pmsg()
                p2p['index'] = event['index']
                p2p['family'] = 2
                p2p['attrs'] = [('P2P_LOCAL', local), ('P2P_REMOTE', remote)]
                await schema.load_netlink('p2p', sources, target, p2p)
            elif iftype == 'veth':
                link = event.get_attr('IFLA_LINK')
                ifname = event.get_attr('IFLA_IFNAME')
                # for veth interfaces, IFLA_LINK points to
                # the peer -- but NOT in automatic updates
                if (not link) and (
                    (target,) in schema.fetch('SELECT f_target FROM SOURCES')
                ):
                    schema.log.debug(f'reload veth {event["index"]}')
                    try:
                        update = await sources[target].api(
                            'link', 'get', index=event['index']
                        )
                        update = tuple(update)[0]
                        return await schema.load_netlink(
                            'interfaces', sources, target, update
                        )
                    except NetlinkError as e:
                        if e.code == errno.ENODEV:
                            schema.log.debug(f"interface has gone: {ifname}")

            if table in schema.spec:
                ifdata = linkinfo.get_attr('IFLA_INFO_DATA')
                if ifdata is not None:
                    ifdata['header'] = {}
                    ifdata['index'] = event['index']
                    await schema.load_netlink(table, sources, target, ifdata)


ip_tunnels = ('gre', 'gretap', 'ip6gre', 'ip6gretap', 'ip6tnl', 'sit', 'ipip')

schema_ifinfmsg = (
    ifinfmsg.sql_schema().push('alt_ifname_list', 'TEXT').unique_index('index')
)

schema_brinfmsg = (
    ifinfmsg.sql_schema()
    .unique_index('index')
    .foreign_key(
        'interface',
        ('f_target', 'f_tflags', 'f_index'),
        ('f_target', 'f_tflags', 'f_index'),
    )
)

schema_p2pmsg = (
    p2pmsg.sql_schema()
    .unique_index('index')
    .foreign_key(
        'interfaces',
        ('f_target', 'f_tflags', 'f_index'),
        ('f_target', 'f_tflags', 'f_index'),
    )
)

schema_af_bridge_vlans = (
    ifinfmsg.af_spec_bridge.vlan_info.sql_schema()
    .push('index', 'INTEGER')
    .unique_index('vid', 'index')
    .foreign_key(
        'af_bridge_ifs',
        ('f_target', 'f_tflags', 'f_index'),
        ('f_target', 'f_tflags', 'f_index'),
    )
)

init = {
    'specs': [
        ['interfaces', schema_ifinfmsg],
        ['af_bridge_ifs', schema_ifinfmsg],
        ['af_bridge_vlans', schema_af_bridge_vlans],
        ['p2p', schema_p2pmsg],
    ],
    'classes': [
        ['interfaces', ifinfmsg],
        ['af_bridge_ifs', ifinfmsg],
        ['vlans', ifinfmsg],
        ['af_bridge_vlans', ifinfmsg.af_spec_bridge.vlan_info],
        ['p2p', p2pmsg],
    ],
    'event_map': {ifinfmsg: [load_ifinfmsg]},
}

ifinfo_names = (
    'bridge',
    'bond',
    'vlan',
    'vxlan',
    'gre',
    'gretap',
    'ip6gre',
    'ip6gretap',
    'ip6tnl',
    'ipip',
    'ipvlan',
    'sit',
    'macvlan',
    'macvtap',
    'tun',
    'vrf',
    'vti',
    'vti6',
)
supported_ifinfo = {x: ifinfmsg.ifinfo.data_map[x] for x in ifinfo_names}
#
# load supported ifinfo
#
for name, data in supported_ifinfo.items():
    name = f'ifinfo_{name}'
    init['classes'].append([name, data])
    schema = (
        data.sql_schema()
        .push('index', 'BIGINT')
        .unique_index('index')
        .foreign_key(
            'interfaces',
            ('f_target', 'f_tflags', 'f_index'),
            ('f_target', 'f_tflags', 'f_index'),
        )
    )
    init['specs'].append([name, schema])


def _cmp_master(self, value):
    if self['master'] == value:
        return True
    elif self['master'] == 0 and value is None:
        dict.__setitem__(self, 'master', None)
        return True
    return False


class Vlan(AsyncObject):
    table = 'af_bridge_vlans'
    msg_class = ifinfmsg.af_spec_bridge.vlan_info
    api = 'vlan_filter'

    @classmethod
    def _count(cls, view):
        if view.chain:
            return view.ndb.schema.fetchone(
                f'SELECT count(*) FROM {view.table} WHERE f_index = ?',
                [view.chain['index']],
            )
        else:
            return view.ndb.schema.fetchone(
                f'SELECT count(*) FROM {view.table}'
            )

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            where = 'WHERE main.f_target = ? AND main.f_index = ?'
            values = [view.chain['target'], view.chain['index']]
        else:
            where = ''
            values = []
        return (where, values)

    @classmethod
    def summary(cls, view):
        req = '''
              SELECT
                  main.f_target, main.f_tflags, main.f_vid,
                  intf.f_IFLA_IFNAME
              FROM
                  af_bridge_vlans AS main
              INNER JOIN
                  interfaces AS intf
              ON
                  main.f_index = intf.f_index
                  AND main.f_target = intf.f_target
              '''
        yield ('target', 'tflags', 'vid', 'ifname')
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

    @staticmethod
    def compare_record(left, right):
        if isinstance(right, int):
            return right == left['vid']

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ifinfmsg.af_spec_bridge.vlan_info
        super(Vlan, self).__init__(*argv, **kwarg)

    def make_req(self, prime):
        ret = {}
        if 'index' in self:
            ret['index'] = self['index']
        ret['vlan_info'] = {'vid': self['vid']}
        if 'flags' in self:
            ret['vlan_info']['flags'] = self['flags']
        return ret

    def make_idx_req(self, prime):
        return self.make_req(prime)


class Interface(AsyncObject):
    table = 'interfaces'
    msg_class = ifinfmsg
    api = 'link'
    key_extra_fields = ['IFLA_IFNAME']
    resolve_fields = ['vxlan_link', 'link', 'master']
    fields_cmp = {'master': _cmp_master}
    fields_load_transform = {
        'alt_ifname_list': lambda x: list(json.loads(x or '[]'))
    }
    field_filter = LinkFieldFilter
    old_ifname = None

    @classmethod
    def _count(cls, view):
        if view.chain:
            return view.ndb.schema.fetchone(
                f'SELECT count(*) FROM {view.table} WHERE f_IFLA_MASTER = ?',
                [view.chain['index']],
            )
        else:
            return view.ndb.schema.fetchone(
                f'SELECT count(*) FROM {view.table}'
            )

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            where = 'WHERE f_target = ? AND f_IFLA_MASTER = ?'
            values = [view.chain['target'], view.chain['index']]
        else:
            where = 'WHERE f_index != 0'
            values = []
        return (where, values)

    @classmethod
    def summary(cls, view):
        req = '''
              SELECT
                  f_target, f_tflags, f_index,
                  f_IFLA_IFNAME, f_IFLA_ADDRESS,
                  f_flags, f_IFLA_INFO_KIND
              FROM
                  interfaces
              '''
        yield (
            'target',
            'tflags',
            'index',
            'ifname',
            'address',
            'flags',
            'kind',
        )
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

    def mark_tflags(self, mark):
        self.schema.execute(
            '''
               UPDATE interfaces SET
                   f_tflags = ?
               WHERE f_index = ? AND f_target = ?
            ''',
            (mark, self['index'], self['target']),
        )

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ifinfmsg
        self.event_map = {ifinfmsg: "load_rtnlmsg"}
        self._alt_ifname_orig = set()
        dict.__setitem__(self, 'alt_ifname_list', list())
        dict.__setitem__(self, 'state', 'unknown')
        warnings = []
        if isinstance(argv[1], dict):
            if 'reuse' in argv[1]:
                warnings.append('ignore IPDB-specific `reuse` keyword')
                del argv[1]['reuse']
            if argv[1].get('create') and 'ifname' not in argv[1]:
                raise Exception('specify at least ifname')
            # type specific cases
            if argv[1].get('kind') == 'tuntap':
                # translate custom tuntap format into the native tun
                warnings.append('translated tuntap ifinfo into tun, no flags')
                argv[1]['kind'] = 'tun'
                if argv[1].get('mode') == 'tun':
                    argv[1]['tun_type'] = 1
                elif argv[1].get('mode') == 'tap':
                    argv[1]['tun_type'] = 2
                else:
                    raise TypeError('tun type error')
                del argv[1]['mode']
                if 'uid' in argv[1]:
                    argv[1]['tun_owner'] = argv[1].pop('uid')
                if 'gid' in argv[1]:
                    argv[1]['tun_owner'] = argv[1].pop('gid')
        super(Interface, self).__init__(*argv, **kwarg)
        for line in warnings:
            self.log.warning(line)

    @property
    def ipaddr(self):
        return self.view.ndb._get_view('addresses', chain=self)

    @property
    def ports(self):
        return self.view.ndb._get_view('interfaces', chain=self)

    @property
    def routes(self):
        return self.view.ndb._get_view('routes', chain=self)

    @property
    def neighbours(self):
        return self.view.ndb._get_view('neighbours', chain=self)

    @property
    def vlans(self):
        return self.view.ndb._get_view('af_bridge_vlans', chain=self)

    @property
    def context(self):
        ctx = {}
        if self.get('target'):
            ctx['target'] = self['target']
        if self.get('index'):
            ctx['index'] = self['index']
        return ctx

    @classmethod
    def compare_record(self, left, right):
        # specific compare
        if isinstance(right, basestring):
            return right == left['ifname'] or right == left['address']

    def add_vlan(self, spec):
        def do_add_vlan(self, mode, spec):
            try:
                method = getattr(self.vlans.create(spec), mode)
                return [method()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_add_vlan, {'spec': spec}))
        return self

    def ensure_vlan(self, spec):
        def do_ensure_vlan(self, mode, spec):
            try:
                method = getattr(self.vlans.create(spec), mode)
                return [method()]
            except KeyError:
                return []
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_ensure_vlan, {'spec': spec}))
        return self

    def del_vlan(self, spec):
        def do_del_vlan(self, mode, spec):
            try:
                method = getattr(self.vlans[spec].remove(), mode)
                return [method()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_del_vlan, {'spec': spec}))
        return self

    def add_neighbour(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_add_neighbour(self, mode, spec):
            try:
                method = getattr(self.neighbours.create(spec), mode)
                return [method()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_add_neighbour, {'spec': spec}))
        return self

    def ensure_neighbour(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_ensure_neighbour(self, mode, spec):
            try:
                method = getattr(self.neighbours.create(spec), mode)
                return [method()]
            except KeyError:
                return []
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_ensure_neighbour, {'spec': spec}))
        return self

    def del_neighbour(self, spec=None, **kwarg):
        spec = spec or dict(kwarg)

        def do_del_neighbour(self, mode, spec):
            ret = []
            if isinstance(spec, basestring):
                specs = [spec]
            elif callable(spec):
                specs = self.neighbours.dump()
                specs.select_records(spec)
                specs.materialize()
            else:
                specs = self.neighbours.dump()
                specs.select_records(**spec)
                specs.materialize()
            for sp in specs:
                try:
                    method = getattr(self.neighbours.locate(sp).remove(), mode)
                    ret.append(method())
                except KeyError:
                    pass
                except Exception as e_s:
                    e_s.trace = traceback.format_stack()
                    ret.append(e_s)
            if not ret:
                ret = KeyError('no neighbour records matched')
            return ret

        self._apply_script.append((do_del_neighbour, {'spec': spec}))
        return self

    def add_ip(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_add_ip(self, mode, spec):
            try:
                method = getattr(self.ipaddr.create(spec), mode)
                return [method()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_add_ip, {'spec': spec}))
        return self

    def ensure_ip(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_ensure_ip(self, mode, spec):
            try:
                method = getattr(self.ipaddr.create(spec), mode)
                return [method()]
            except KeyError:
                return []
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_ensure_ip, {'spec': spec}))
        return self

    def del_ip(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_del_ip(self, mode, spec):
            ret = []
            if isinstance(spec, basestring):
                specs = [spec]
            elif callable(spec):
                specs = self.ipaddr.dump()
                specs.select_records(spec)
                specs.materialize()
            else:
                specs = self.ipaddr.dump()
                specs.select_records(**spec)
                specs.materialize()
            for sp in specs:
                try:
                    method = getattr(self.ipaddr.locate(sp).remove(), mode)
                    ret.append(method())
                except KeyError:
                    pass
                except Exception as e_s:
                    e_s.trace = traceback.format_stack()
                    ret.append(e_s)
            if not ret:
                ret = [KeyError('no address records matched')]
            return ret

        self._apply_script.append((do_del_ip, {'spec': spec}))
        return self

    def add_port(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_add_port(self, mode, spec):
            try:
                port = self.view[spec]
                if port['target'] != self['target']:
                    raise ValueError('target must be the same')
                port['master'] = self['index']
                return [getattr(port, mode)()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_add_port, {'spec': spec}))
        return self

    def del_port(self, spec=None, **kwarg):
        spec = spec or kwarg

        def do_del_port(self, mode, spec):
            try:
                port = self.view[spec]
                if port['master'] != self['index']:
                    raise ValueError('wrong port master index')
                if port['target'] != self['target']:
                    raise ValueError('target must be the same')
                port['master'] = 0
                return [getattr(port, mode)()]
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return [e_s]

        self._apply_script.append((do_del_port, {'spec': spec}))
        return self

    def add_altname(self, ifname):
        new_list = set(self['alt_ifname_list'])
        new_list.add(ifname)
        self['alt_ifname_list'] = list(new_list)
        return self

    def del_altname(self, ifname):
        new_list = set(self['alt_ifname_list'])
        new_list.remove(ifname)
        self['alt_ifname_list'] = list(new_list)
        return self

    def __setitem__(self, key, value):
        if key == 'peer':
            dict.__setitem__(self, key, value)
        elif key == 'ifname':
            if value in self['alt_ifname_list']:
                self.del_altname(value)
            if key in self and self.old_ifname is None:
                self.old_ifname = self[key]
            super(Interface, self).__setitem__(key, value)
        elif key == 'target' and self.state == 'invalid':
            dict.__setitem__(self, key, value)
        elif key == 'net_ns_fd' and self.state == 'invalid':
            dict.__setitem__(self, 'target', value)
        elif (
            key == 'target' and self.get('target') and self['target'] != value
        ):
            super(Interface, self).__setitem__('net_ns_fd', value)
        else:
            super(Interface, self).__setitem__(key, value)

    @classmethod
    def spec_normalize(cls, spec):
        '''
        Interface key normalization::

            { ... }  ->  { ... }
            "eth0"   ->  {"ifname": "eth0", ...}
            1        ->  {"index": 1, ...}

        '''
        if isinstance(spec, basestring):
            return {'ifname': spec}
        elif isinstance(spec, int):
            return {'index': spec}
        elif isinstance(spec, ifinfmsg):
            ret = {'ifname': spec.get('ifname')}
            if spec.get('index') != 0:
                ret['index'] = spec.get('index')
            return ret
        return spec

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': self.ndb.localhost}
        if isinstance(key, basestring):
            ret_key['ifname'] = key
        elif isinstance(key, int):
            ret_key['index'] = key
        return super(Interface, self).complete_key(ret_key)

    async def is_peer(self, other):
        '''Evaluate whether the given interface "points at" this one.'''
        if other['kind'] == 'vlan':
            return (
                other['target'] == self['target']
                and other['link'] == self['index']
            )

        elif other['kind'] == 'vxlan':
            return (
                other['target'] == self['target']
                and other['vxlan_link'] == self['index']
            )

        elif other['kind'] == self['kind'] == 'veth':
            other_link = other.get('link')

            if other_link != self['index']:
                return False

            other_link_netnsid = other.get('link_netnsid')
            if other_link_netnsid is not None:
                other_source = other.sources[other['target']]
                info = await other_source.api(
                    'get_netnsid',
                    pid=os.getpid(),
                    target_nsid=other_link_netnsid,
                )
                return info['current_nsid'] == other_link_netnsid

            return self['target'] == other['target']

    def set_xdp_fd(self, fd):
        self.sources[self['target']].api(
            'link', 'set', index=self['index'], xdp_fd=fd
        )

    async def snapshot(self, ctxid=None):
        # 1. make own snapshot
        snp = await super().snapshot(ctxid=ctxid)
        # 2. collect dependencies and store in self.snapshot_deps
        for spec in self.ndb.interfaces.asyncore.getmany(
            {'IFLA_MASTER': self['index']}
        ):
            # bridge ports
            link = type(self)(self.view, spec)
            snp.snapshot_deps.append((link, await link.snapshot()))
        for spec in self.ndb.interfaces.asyncore.getmany(
            {'IFLA_LINK': self['index']}
        ):
            link = type(self)(self.view, spec)
            # vlans & veth
            if await self.is_peer(link) and not await link.is_peer(self):
                snp.snapshot_deps.append((link, await link.snapshot()))
        # return the root node
        return snp

    def make_req(self, prime):
        req = super(Interface, self).make_req(prime)
        #
        # --> link('set', ...)
        if self.state == 'system':
            req['master'] = self['master']
            #
            # FIXME: make type plugins?
            kind = self['kind']
            if kind in ip_tunnels:
                req['kind'] = kind
                for key in self:
                    if (
                        key.startswith(f'{kind}_')
                        and key not in req
                        and self[key]
                    ):
                        req[key] = self[key]
        return req

    async def apply_altnames(
        self, alt_ifname_setup, alt_ifname_current, old_ifname=None
    ):
        if 'alt_ifname_list' in self.changed:
            self.changed.remove('alt_ifname_list')
        if alt_ifname_current is None:
            # load the current state
            await self.load_from_system()
            self.load_sql(set_state=False)
            alt_ifname_current = set(self['alt_ifname_list'])

        alt_ifname_remove = alt_ifname_current - alt_ifname_setup
        alt_ifname_add = alt_ifname_setup - alt_ifname_current
        for ifname in alt_ifname_remove:
            await self.sources[self['target']].api(
                'link', 'property_del', index=self['index'], altname=ifname
            )
        for ifname in alt_ifname_add:
            await self.sources[self['target']].api(
                'link', 'property_add', index=self['index'], altname=ifname
            )
        # reload alt ifnames from the system to check the state
        await self.load_from_system()
        self.load_sql(set_state=False)
        if old_ifname is not None and old_ifname in self['alt_ifname_list']:
            alt_ifname_setup.add(old_ifname)
        if set(self['alt_ifname_list']) != alt_ifname_setup:
            raise Exception('could not setup alt ifnames')

    async def apply(self, rollback=False, req_filter=None, mode='apply'):
        # translate string link references into numbers
        for key in ('link', 'master'):
            if key in self and isinstance(self[key], basestring):
                self[key] = self.ndb.interfaces.asyncore[self[key]]['index']
        setns = self.state.get() == 'setns'
        remove = self.state.get() == 'remove'
        alt_ifname_setup = set(self['alt_ifname_list'])
        old_ifname = self.old_ifname if 'ifname' in self.changed else None
        try:
            if 'index' in self and (
                self.old_ifname or 'alt_ifname_list' in self.changed
            ):
                await self.apply_altnames(alt_ifname_setup, None)
            if 'alt_ifname_list' in self.changed:
                self.changed.remove('alt_ifname_list')
            await super().apply(rollback, req_filter, mode)
            if setns and self['net_ns_fd'] in self.sources:
                self.load_value('target', self['net_ns_fd'])
                dict.__setitem__(self, 'net_ns_fd', None)
                for link in await self.sources[self['target']].api(
                    'link', 'get', ifname=self['ifname']
                ):
                    # after interface move the name is the same,
                    # but the index may change
                    #
                    # in this case .load_sql() will not update
                    # the object, and the engine will try to apply
                    # the interface's attributes to another interface
                    # with the same index as our old one
                    #
                    # so resync the index first
                    #
                    # Bug-Url: https://github.com/svinota/pyroute2/issues/1181
                    #
                    self.load_value('index', link['index'])
                    break
                spec = self.load_sql()
                if spec:
                    self.state.set('system')
            if not remove and self.state != 'invalid':
                await self.apply_altnames(
                    alt_ifname_setup, set(self['alt_ifname_list']), old_ifname
                )

        except NetlinkError as e:
            if (
                e.code == 95
                and self.get('master') is not None
                and self.get('master') > 0
                and self.state == 'invalid'
            ):
                #
                # on some old kernels it is impossible to create
                # interfaces with master set; attempt to do it in
                # two steps
                def req_filter(req):
                    return dict(
                        [
                            x
                            for x in req.items()
                            if not x[0].startswith('master')
                        ]
                    )

                await self.apply(rollback, req_filter, mode)
                await self.apply(rollback, None, mode)

            elif (
                e.code == 95
                and self.get('br_vlan_filtering') is not None
                and self.get('br_vlan_filtering') == 0
            ):
                #
                # if vlan filtering is not enabled, then the parameter
                # is reported by netlink, but not accepted upon bridge
                # creation, so simply strip it
                def req_filter(req):
                    return dict(
                        [
                            x
                            for x in req.items()
                            if not x[0].startswith('br_vlan_')
                        ]
                    )

                await self.apply(rollback, req_filter, mode)
            else:
                raise
        finally:
            self.old_ifname = None
        if ('net_ns_fd' in self.get('peer', {})) and (
            self['peer']['net_ns_fd'] in self.view.ndb.sources
        ):
            # wait for the peer in net_ns_fd, only if the netns
            # is connected to the NDB instance
            await self.view.wait(
                target=self['peer']['net_ns_fd'],
                ifname=self['peer']['ifname'],
                timeout=5,
            )
        return self

    async def hook_apply(self, method, **spec):
        if method == 'set':
            if self['kind'] == 'bridge':
                keys = filter(lambda x: x.startswith('br_'), self.changed)
                if keys:
                    req = {
                        'index': self['index'],
                        'kind': 'bridge',
                        'family': AF_BRIDGE,
                    }
                    for key in keys:
                        req[key] = self[key]
                    await self.sources[self['target']].api(
                        self.api, method, **req
                    )
                    # FIXME: make a reasonable shortcut for this
                    await self.load_from_system()
            elif self['kind'] in ip_tunnels and self['state'] == 'down':
                # force reading attributes for tunnels in the down state
                await self.load_from_system()
        elif method == 'add':
            if self['kind'] == 'tun':
                self.load_sql()
                await self.load_event.wait()
                if 'index' not in self:
                    raise NetlinkError(errno.EAGAIN)
                update = await self.sources[self['target']].api(
                    self.api, 'get', index=self['index']
                )
                self.ndb._event_queue.put(update)

    async def load_from_system(self):
        self.load_event.clear()
        await self.sources[self['target']].api(
            self.api, 'get', index=self['index']
        )
        await self.load_event.wait()

    def load_sql(self, *argv, **kwarg):
        spec = super(Interface, self).load_sql(*argv, **kwarg)
        if spec:
            tname = f'ifinfo_{self["kind"]}'
            if tname in self.schema.compiled:
                names = self.schema.compiled[tname]['norm_names']
                spec = self.ndb.schema.fetchone(
                    f'SELECT * from {tname} WHERE f_index = ?',
                    (self['index'],),
                )
                if spec:
                    self.update(dict(zip(names, spec)))
        return spec

    async def load_rtnlmsg(self, *argv, **kwarg):
        await super().load_rtnlmsg(*argv, **kwarg)

    def key_repr(self):
        return '%s/%s' % (
            self.get('target', ''),
            self.get('ifname', self.get('index', '')),
        )


class SyncInterface(RTNL_Object):

    def __init__(self, event_loop, obj, class_map=None, flags=Flags.RO):
        super().__init__(event_loop, obj, class_map, flags)
        self.ipaddr = SyncView(
            event_loop, obj.ipaddr, self.class_map, self.flags
        )
        self.neighbours = SyncView(
            event_loop, obj.neighbours, self.class_map, self.flags
        )
        self.ports = SyncView(
            event_loop, obj.ports, self.class_map, self.flags
        )
        self.routes = SyncView(
            event_loop, obj.routes, self.class_map, self.flags
        )
        self.vlans = SyncView(
            event_loop, obj.vlans, self.class_map, self.flags
        )

    @property
    def state(self):
        return self.asyncore.state

    def add_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.add_ip, spec, **kwarg)
        return self

    def del_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.del_ip, spec, **kwarg)
        return self

    def ensure_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.ensure_ip, spec, **kwarg)
        return self

    def add_neighbour(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.add_neighbour, spec, **kwarg)
        return self

    def del_neighbour(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.del_neighbour, spec, **kwarg)
        return self

    def ensure_neighbour(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.ensure_neighbour, spec, **kwarg)
        return self

    def add_port(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.add_port, spec, **kwarg)
        return self

    def del_port(self, spec=None, **kwarg):
        self._main_sync_call(self.asyncore.del_port, spec, **kwarg)
        return self

    def add_altname(self, ifname):
        self._main_sync_call(self.asyncore.add_altname, ifname)
        return self

    def del_altname(self, ifname):
        self._main_sync_call(self.asyncore.del_altname, ifname)
        return self

    def load_from_system(self):
        self._main_async_call(self.asyncore.load_from_system)
