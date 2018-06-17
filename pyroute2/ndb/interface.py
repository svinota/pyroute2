import weakref
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


class Interface(dict):

    table = 'interfaces'

    def __init__(self, db, key):
        self.db = db
        self.kspec = ('target', ) + db.indices[self.table]
        self.schema = ('target', ) + \
            tuple(db.schema[self.table].keys())
        self.names = tuple((ifinfmsg.nla2name(x) for x in self.schema))
        self.key = self.complete_key(key)
        self.changed = set()
        self.load_sql()

    @property
    def event_map(self):
        #
        # return event_map on demand -- decrease the number of
        # references for the garbage collector
        #
        return {ifinfmsg: self.load_ifinfmsg}

    def __setitem__(self, key, value):
        self.changed.add(key)
        dict.__setitem__(self, key, value)

    def snapshot(self):
        snp = type(self)(self.db, self.key)
        self.db.save_deps(self.table, id(snp), weakref.ref(snp))
        return snp

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

    def update(self, data):
        for key, value in data.items():
            self.load_value(key, value)

    def load_value(self, key, value):
        if key not in self.changed:
            dict.__setitem__(self, key, value)

    def load_ifinfmsg(self, target, event):
        # TODO: partial match (object rename / restore)
        # ...

        # full match
        for name, value in self.key.items():
            if name == 'target':
                if value != target:
                    return
            elif value != (event.get_attr(name) or event.get(name)):
                return
        #
        # load the event
        for name in self.schema:
            value = event.get_attr(name) or event.get(name)
            if value is not None:
                self.load_value(ifinfmsg.nla2name(name), value)

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
