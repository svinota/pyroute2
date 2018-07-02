from pyroute2.ndb.rtnl_object import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


class Interface(RTNL_Object):

    table = 'interfaces'
    msg_class = ifinfmsg
    api = 'link'
    summary = '''
              SELECT
                  f_target, f_index, f_IFLA_IFNAME,
                  f_IFLA_ADDRESS, f_flags
              FROM
                  interfaces
              '''
    summary_header = ('target', 'index', 'ifname', 'lladdr', 'flags')

    def __init__(self, view, key, ctxid=None):
        self.event_map = {ifinfmsg: "load_rtnlmsg"}
        super(Interface, self).__init__(view, key, ifinfmsg, ctxid)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['IFLA_IFNAME'] = key
        elif isinstance(key, int):
            ret_key['index'] = key

        fetch = []
        for name in self.kspec:
            if name not in ret_key:
                fetch.append('f_%s' % name)

        if fetch:
            keys = []
            values = []
            for name, value in ret_key.items():
                keys.append('f_%s = %s' % (name, self.schema.plch))
                values.append(value)
            spec = (self
                    .schema
                    .execute('SELECT %s FROM interfaces WHERE %s' %
                             (' , '.join(fetch), ' AND '.join(keys)),
                             values)
                    .fetchone())
            for name, value in zip(fetch, spec):
                ret_key[name[2:]] = value

        return ret_key

    def load_sql(self, *argv, **kwarg):
        super(Interface, self).load_sql(*argv, **kwarg)
        self.load_value('state', 'up' if self['flags'] & 1 else 'down')

    def load_rtnl(self, *argv, **kwarg):
        super(Interface, self).load_rtnl(*argv, **kwarg)
        self.load_value('state', 'up' if self['flags'] & 1 else 'down')


class Bridge(Interface):

    table = 'bridge'
    summary = '''
              SELECT
                  f_target, f_index, f_IFLA_IFNAME,
                  f_IFLA_ADDRESS, f_IFLA_BR_STP_STATE,
                  f_IFLA_BR_VLAN_FILTERING
              FROM
                  bridge
              '''
    summary_header = ('target', 'index', 'ifname',
                      'lladdr', 'stp', 'vlan_filtering')


class Vlan(Interface):

    table = 'vlan'
    summary = '''
              SELECT
                  f_target, f_index, f_IFLA_IFNAME,
                  f_IFLA_ADDRESS, f_IFLA_LINK, f_IFLA_VLAN_ID
              FROM
                  vlan
              '''
    summary_header = ('target', 'index', 'ifname',
                      'lladdr', 'master', 'vlan')
