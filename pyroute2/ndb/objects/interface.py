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

import weakref
import traceback
from pyroute2.config import AF_BRIDGE
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


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
    summary = '''
              SELECT
                  a.f_target, a.f_tflags, a.f_index, a.f_IFLA_IFNAME,
                  a.f_IFLA_ADDRESS, a.f_flags, a.f_IFLA_INFO_KIND
              FROM
                  interfaces AS a
              '''
    table_alias = 'a'
    summary_header = ('target',
                      'tflags',
                      'index',
                      'ifname',
                      'lladdr',
                      'flags',
                      'kind')
    fields_cmp = {'master': _cmp_master}

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
        return (self
                .view
                .ndb
                ._get_view('addresses',
                           chain=self,
                           match_src=[weakref.proxy(self),
                                      {'index':
                                       self.get('index', 0),
                                       'target': self['target']}],
                           match_pairs={'index': 'index',
                                        'target': 'target'}))

    @property
    def ports(self):
        return (self
                .view
                .ndb
                ._get_view('interfaces',
                           chain=self,
                           match_src=[weakref.proxy(self),
                                      {'index':
                                       self.get('index', 0),
                                       'target': self['target']}],
                           match_pairs={'master': 'index',
                                        'target': 'target'}))

    @property
    def routes(self):
        return (self
                .view
                .ndb
                ._get_view('routes',
                           chain=self,
                           match_src=[weakref.proxy(self),
                                      {'index':
                                       self.get('index', 0),
                                       'target': self['target']}],
                           match_pairs={'oif': 'index',
                                        'target': 'target'}))

    @property
    def neighbours(self):
        return (self
                .view
                .ndb
                ._get_view('neighbours',
                           chain=self,
                           match_src=[weakref.proxy(self),
                                      {'index':
                                       self.get('index', 0),
                                       'target': self['target']}],
                           match_pairs={'ifindex': 'index',
                                        'target': 'target'}))

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
            # vlans
            link = type(self)(self.view, spec)
            snp.snapshot_deps.append((link, link.snapshot()))
        # return the root node
        return snp

    def make_req(self, prime):
        req = super(Interface, self).make_req(prime)
        if self.state == 'system':  # --> link('set', ...)
            req['master'] = self['master']
        return req

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
                    self.ndb._event_queue.put((self['target'], update))

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

    def load_rtnlmsg(self, *argv, **kwarg):
        super(Interface, self).load_rtnlmsg(*argv, **kwarg)

    def key_repr(self):
        return '%s/%s' % (self.get('target', ''),
                          self.get('ifname', self.get('index', '')))
