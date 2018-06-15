from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


class Interface(dict):

    def __init__(self, db, key):
        self.db = db
        self.kspec = ('target', ) + db.index['interfaces']
        self.schema = ('target', ) + \
            tuple(db.schema['interfaces'].keys())
        self.names = (ifinfmsg.nla2name(x) for x in self.schema)
        self.key = self.complete_key(key)
        self.load_sql()

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
                keys.append('f_%s = ?' % name)
                values.append(value)
            spec = (self
                    .db
                    .execute('SELECT %s FROM interfaces WHERE %s' %
                             (' , '.join(fetch), ' AND '.join(keys)),
                             values)
                    .fetchone())
            for name, value in zip(fetch, spec):
                ret_key[name[2:]] = value

        return ret_key

    def load_rtnl(self, event):
        pass

    def load_sql(self):
        keys = []
        values = []
        for name, value in self.key.items():
            keys.append('f_%s = ?' % name)
            values.append(value)
        spec = (self
                .db
                .execute('SELECT * FROM interfaces WHERE %s' %
                         ' AND '.join(keys), values)
                .fetchone())
        self.update(dict(zip(self.names, spec)))
        return self
