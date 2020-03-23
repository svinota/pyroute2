'''
List interfaces
===============

List interface keys::

    with NDB(log='on') as ndb:
        for key in ndb.interfaces:
            print(key)

NDB views support some dict methods: `items()`, `values()`, `keys()`::

    with NDB(log='on') as ndb:
        for key, nic in ndb.interfaces.items():
            nic.set('state', 'up')
            nic.commit()

Get interface objects
=====================

The keys may be used as selectors to get interface objects::

    with NDB(log='on') as ndb:
        for key in ndb.interfaces:
            print(ndb.interfaces[key])

Also possible selector formats are `dict()` and simple string. The latter
means the interface name::

    eth0 = ndb.interfaces['eth0']

Dict selectors are necessary to get interfaces by other properties::

    wrk1_eth0 = ndb.interfaces[{'target': 'worker1.sample.com',
                                'ifname': 'eth0'}]

    wrk2_eth0 = ndb.interfaces[{'target': 'worker2.sample.com',
                                'address': '52:54:00:22:a1:b7'}]

Change nic properties
=====================

Changing MTU and MAC address::

    with NDB(log='on') as ndb:
        with ndb.interfaces['eth0'] as eth0:
            eth0['mtu'] = 1248
            eth0['address'] = '00:11:22:33:44:55'
        # --> <-- eth0.commit() is called by the context manager
    # --> <-- ndb.close() is called by the context manager

One can change a property either using the assignment statement, or
using the `.set()` routine::

    # same code
    with NDB(log='on') as ndb:
        with ndb.interfaces['eth0'] as eth0:
            eth0.set('mtu', 1248)
            eth0.set('address', '00:11:22:33:44:55')

The `.set()` routine returns the object itself, that makes possible
chain calls::

    # same as above
    with NDB(log='on') as ndb:
        with ndb.interfaces['eth0'] as eth0:
            eth0.set('mtu', 1248).set('address', '00:11:22:33:44:55')

    # or
    with NDB(log='on') as ndb:
        with ndb.interfaces['eth0'] as eth0:
            (eth0
             .set('mtu', 1248)
             .set('address', '00:11:22:33:44:55'))

    # or without the context manager, call commit() explicitly
    with NDB(log='on') as ndb:
        (ndb
         .interfaces['eth0']
         .set('mtu', 1248)
         .set('address', '00:11:22:33:44:55')
         .commit())

Create virtual interfaces
=========================

Create a bridge and add a port, `eth0`::

    (ndb
     .interfaces
     .create(ifname='br0', kind='bridge')
     .commit())

    (ndb
     .interfaces['eth0']
     .set('master', ndb.interfaces['br0']['index'])
     .commit())

'''

import traceback
from collections import OrderedDict
from pyroute2.config import AF_BRIDGE
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.p2pmsg import p2pmsg
from pyroute2.netlink.exceptions import NetlinkError


def load_ifinfmsg(schema, target, event):
    #
    # link goes down: flush all related routes
    #
    if not event['flags'] & 1:
        schema.execute('DELETE FROM routes WHERE '
                       'f_target = %s AND '
                       'f_RTA_OIF = %s OR f_RTA_IIF = %s'
                       % (schema.plch, schema.plch, schema.plch),
                       (target, event['index'], event['index']))
    #
    # ignore wireless updates
    #
    if event.get_attr('IFLA_WIRELESS'):
        return
    #
    # AF_BRIDGE events
    #
    if event['family'] == AF_BRIDGE:
        #
        # bypass for now
        #
        schema.load_netlink('af_bridge_ifs', target, event)
        vlans = (event
                 .get_attr('IFLA_AF_SPEC')
                 .get_attrs('IFLA_BRIDGE_VLAN_INFO'))
        for v in vlans:
            v['index'] = event['index']
            v['header'] = {'type': event['header']['type']}
            schema.load_netlink('af_bridge_vlans', target, v)

        return

    schema.load_netlink('interfaces', target, event)
    #
    # load ifinfo, if exists
    #
    if not event['header'].get('type', 0) % 2:
        linkinfo = event.get_attr('IFLA_LINKINFO')
        if linkinfo is not None:
            iftype = linkinfo.get_attr('IFLA_INFO_KIND')
            table = 'ifinfo_%s' % iftype
            if iftype == 'gre':
                ifdata = linkinfo.get_attr('IFLA_INFO_DATA')
                local = ifdata.get_attr('IFLA_GRE_LOCAL')
                remote = ifdata.get_attr('IFLA_GRE_REMOTE')
                p2p = p2pmsg()
                p2p['index'] = event['index']
                p2p['family'] = 2
                p2p['attrs'] = [('P2P_LOCAL', local),
                                ('P2P_REMOTE', remote)]
                schema.load_netlink('p2p', target, p2p)
            elif iftype == 'veth':
                link = event.get_attr('IFLA_LINK')
                # for veth interfaces, IFLA_LINK points to
                # the peer -- but NOT in automatic updates
                if (not link) and \
                        (target in schema.ndb.sources.keys()):
                    schema.log.debug('reload veth %s' % event['index'])
                    update = (schema
                              .ndb
                              .sources[target]
                              .api('link', 'get', index=event['index']))
                    update = tuple(update)[0]
                    return schema.load_netlink('interfaces', target, update)

            if table in schema.spec:
                ifdata = linkinfo.get_attr('IFLA_INFO_DATA')
                ifdata['header'] = {}
                ifdata['index'] = event['index']
                schema.load_netlink(table, target, ifdata)


init = {'specs': [['interfaces', OrderedDict(ifinfmsg.sql_schema())],
                  ['af_bridge_ifs', OrderedDict(ifinfmsg.sql_schema())],
                  ['af_bridge_vlans', OrderedDict(ifinfmsg
                                                  .af_spec_bridge
                                                  .vlan_info
                                                  .sql_schema() +
                                                  [(('index', ), 'INTEGER')])],
                  ['p2p', OrderedDict(p2pmsg.sql_schema())]],
        'classes': [['interfaces', ifinfmsg],
                    ['af_bridge_ifs', ifinfmsg],
                    ['af_bridge_vlans', ifinfmsg.af_spec_bridge.vlan_info],
                    ['p2p', p2pmsg]],
        'indices': [['interfaces', ('index', )],
                    ['af_bridge_ifs', ('index', )],
                    ['af_bridge_vlans', ('vid', 'index')],
                    ['p2p', ('index', )]],
        'foreign_keys': [['af_bridge_ifs', [{'fields': ('f_target',
                                                        'f_tflags',
                                                        'f_index'),
                                             'parent_fields': ('f_target',
                                                               'f_tflags',
                                                               'f_index'),
                                             'parent': 'interfaces'}]],
                         ['af_bridge_vlans', [{'fields': ('f_target',
                                                          'f_tflags',
                                                          'f_index', ),
                                               'parent_fields': ('f_target',
                                                                 'f_tflags',
                                                                 'f_index', ),
                                               'parent': 'af_bridge_ifs'}]],
                         ['p2p', [{'fields': ('f_target',
                                              'f_tflags',
                                              'f_index'),
                                   'parent_fields': ('f_target',
                                                     'f_tflags',
                                                     'f_index'),
                                   'parent': 'interfaces'}]]],
        'event_map': {ifinfmsg: [load_ifinfmsg]}}

ifinfo_names = ('bridge',
                'bond',
                'vlan',
                'vxlan',
                'gre',
                'vrf',
                'vti',
                'vti6')
supported_ifinfo = {x: ifinfmsg.ifinfo.data_map[x] for x in ifinfo_names}
#
# load supported ifinfo
#
for (name, data) in supported_ifinfo.items():
    name = 'ifinfo_%s' % name
    #
    # classes
    #
    init['classes'].append([name, data])
    #
    # indices
    #
    init['indices'].append([name, ('index', )])
    #
    # spec
    #
    init['specs'].append([name, OrderedDict(data.sql_schema() +
                                            [(('index', ), 'BIGINT')])])
    #
    # foreign keys
    #
    init['foreign_keys'].append([name, [{'fields': ('f_target',
                                                    'f_tflags',
                                                    'f_index'),
                                         'parent_fields': ('f_target',
                                                           'f_tflags',
                                                           'f_index'),
                                         'parent': 'interfaces'}]])


def _cmp_master(self, value):
    if self['master'] == value:
        return True
    elif self['master'] == 0 and value is None:
        dict.__setitem__(self, 'master', None)
        return True
    return False


class Interface(RTNL_Object):

    table = 'interfaces'
    msg_class = ifinfmsg
    api = 'link'
    key_extra_fields = ['IFLA_IFNAME']
    fields_cmp = {'master': _cmp_master}

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            plch = view.ndb.schema.plch
            where = '''
                    WHERE
                        f_target = %s AND
                        f_IFLA_MASTER = %s
                    ''' % (plch, plch)
            values = [view.chain['target'], view.chain['index']]
        else:
            where = ''
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
        yield ('target', 'tflags', 'index',
               'ifname', 'lladdr',
               'flags', 'kind')
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

    def mark_tflags(self, mark):
        plch = (self.schema.plch, ) * 3
        self.schema.execute('''
                            UPDATE interfaces SET
                                f_tflags = %s
                            WHERE f_index = %s AND f_target = %s
                            ''' % plch, (mark, self['index'], self['target']))

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ifinfmsg
        self.event_map = {ifinfmsg: "load_rtnlmsg"}
        dict.__setitem__(self, 'flags', 0)
        dict.__setitem__(self, 'state', 'unknown')
        if isinstance(argv[1], dict) and argv[1].get('create'):
            if 'ifname' not in argv[1]:
                raise Exception('specify at least ifname')
        super(Interface, self).__init__(*argv, **kwarg)

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
    def context(self):
        ctx = {}
        if self.get('target'):
            ctx['target'] = self['target']
        if self.get('index'):
            ctx['index'] = self['index']
        return ctx

    @classmethod
    def adjust_spec(cls, spec, context):
        if isinstance(spec, basestring):
            ret = {'ifname': spec}
        else:
            ret = dict(spec)
        ret.update(context)
        return ret

    def add_ip(self, spec):
        def do_add_ip(self, spec):
            try:
                self.ipaddr.create(spec).apply()
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return e_s
        self._apply_script.append((do_add_ip, (self, spec), {}))
        return self

    def del_ip(self, spec):
        def do_del_ip(self, spec):
            try:
                ret = self.ipaddr[spec].remove().apply()
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return e_s
            return ret.last_save
        self._apply_script.append((do_del_ip, (self, spec), {}))
        return self

    def add_port(self, spec):
        def do_add_port(self, spec):
            try:
                port = self.view[spec]
                assert port['target'] == self['target']
                port['master'] = self['index']
                port.apply()
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return e_s
            return port.last_save
        self._apply_script.append((do_add_port, (self, spec), {}))
        return self

    def del_port(self, spec):
        def do_del_port(self, spec):
            try:
                port = self.view[spec]
                assert port['master'] == self['index']
                assert port['target'] == self['target']
                port['master'] = 0
                port.apply()
            except Exception as e_s:
                e_s.trace = traceback.format_stack()
                return e_s
            return port.last_save
        self._apply_script.append((do_del_port, (self, spec), {}))
        return self

    def __setitem__(self, key, value):
        if key == 'peer':
            dict.__setitem__(self, key, value)
        elif key == 'target' and self.state == 'invalid':
            dict.__setitem__(self, key, value)
        elif key == 'net_ns_fd' and self.state == 'invalid':
            dict.__setitem__(self, 'target', value)
        elif key == 'target' and \
                self.get('target') and \
                self['target'] != value:
            super(Interface, self).__setitem__('net_ns_fd', value)
        else:
            super(Interface, self).__setitem__(key, value)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['ifname'] = key
        elif isinstance(key, int):
            ret_key['index'] = key

        return super(Interface, self).complete_key(ret_key)

    def snapshot(self, ctxid=None):
        # 1. make own snapshot
        snp = super(Interface, self).snapshot(ctxid=ctxid)
        # 2. collect dependencies and store in self.snapshot_deps
        for spec in (self
                     .ndb
                     .interfaces
                     .getmany({'IFLA_MASTER': self['index']})):
            # bridge ports
            link = type(self)(self.view, spec)
            snp.snapshot_deps.append((link, link.snapshot()))
        for spec in (self
                     .ndb
                     .interfaces
                     .getmany({'IFLA_LINK': self['index']})):
            # vlans & veth
            if self.get('link') != spec['index']:
                link = type(self)(self.view, spec)
                snp.snapshot_deps.append((link, link.snapshot()))
        # return the root node
        return snp

    def make_req(self, prime):
        req = super(Interface, self).make_req(prime)
        if self.state == 'system':  # --> link('set', ...)
            req['master'] = self['master']
        return req

    def apply(self, rollback=False, fallback=False):
        # translate string link references into numbers
        for key in ('link', ):
            if key in self and isinstance(self[key], basestring):
                self[key] = self.ndb.interfaces[self[key]]['index']
        setns = self.state.get() == 'setns'
        try:
            super(Interface, self).apply(rollback)
        except NetlinkError as e:
            if e.code == 95 and \
                    'master' in self and \
                    self.state == 'invalid':
                key = dict(self)
                key['create'] = True
                del key['master']
                fb = type(self)(self.view, key)
                fb.register()
                fb.apply(rollback)
                fb.set('master', self['master'])
                fb.apply(rollback)
                del fb
                self.apply()
            else:
                raise
        if setns:
            self.load_value('target', self['net_ns_fd'])
            dict.__setitem__(self, 'net_ns_fd', None)
            spec = self.load_sql()
            if spec:
                self.state.set('system')
        return self

    def hook_apply(self, method, **spec):
        if method == 'set':
            if self['kind'] == 'bridge':
                keys = filter(lambda x: x.startswith('br_'), self.changed)
                if keys:
                    req = {'index': self['index'],
                           'kind': 'bridge',
                           'family': AF_BRIDGE}
                    for key in keys:
                        req[key] = self[key]
                    (self
                     .sources[self['target']]
                     .api(self.api, method, **req))
                    update = (self
                              .sources[self['target']]
                              .api(self.api, 'get',
                                   **{'index': self['index']}))
                    self.ndb._event_queue.put(update)

    def load_sql(self, *argv, **kwarg):
        spec = super(Interface, self).load_sql(*argv, **kwarg)
        if spec:
            tname = 'ifinfo_%s' % self['kind']
            if tname in self.schema.compiled:
                names = self.schema.compiled[tname]['norm_names']
                spec = (self
                        .ndb
                        .schema
                        .fetchone('SELECT * from %s WHERE f_index = %s' %
                                  (tname, self.schema.plch),
                                  (self['index'], )))
                if spec:
                    self.update(dict(zip(names, spec)))
        return spec

    def load_rtnlmsg(self, *argv, **kwarg):
        super(Interface, self).load_rtnlmsg(*argv, **kwarg)

    def key_repr(self):
        return '%s/%s' % (self.get('target', ''),
                          self.get('ifname', self.get('index', '')))
