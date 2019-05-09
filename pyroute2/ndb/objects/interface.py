import weakref
from pyroute2.config import AF_BRIDGE
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


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
        self.load_value('state', 'up' if self['flags'] & 1 else 'down')

    def load_rtnlmsg(self, *argv, **kwarg):
        super(Interface, self).load_rtnlmsg(*argv, **kwarg)
        self.load_value('state', 'up' if self['flags'] & 1 else 'down')

    def key_repr(self):
        return '%s/%s' % (self.get('target', ''),
                          self.get('ifname', self.get('index', '')))
