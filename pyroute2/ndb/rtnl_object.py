import weakref


class RTNL_Object(dict):

    table = None
    db = None
    event_map = None
    summary = None
    summary_header = None
    dump = None
    dump_header = None
    dump_pre = []
    dump_post = []

    def __init__(self, db, key, iclass):
        self.db = db
        self.changed = set()
        self.iclass = iclass
        self.kspec = ('target', ) + db.indices[self.table]
        self.schema = ('target', ) + \
            tuple(db.schema[self.table].keys())
        self.names = tuple((iclass.nla2name(x) for x in self.schema))
        self.key = self.complete_key(key)
        self.load_sql()

    def __hash__(self):
        return id(self)

    def __setitem__(self, key, value):
        self.changed.add(key)
        dict.__setitem__(self, key, value)

    def snapshot(self):
        snp = type(self)(self.db, self.key)
        self.db.save_deps(self.table, id(snp), weakref.ref(snp))
        return snp

    def complete_key(self, key):
        fetch = []
        for name in self.kspec:
            if name not in key:
                fetch.append('f_%s' % name)

        if fetch:
            keys = []
            values = []
            for name, value in key.items():
                keys.append('f_%s = ?' % name)
                values.append(value)
            spec = (self
                    .db
                    .execute('SELECT %s FROM %s WHERE %s' %
                             (' , '.join(fetch),
                              self.table,
                              ' AND '.join(keys)),
                             values)
                    .fetchone())
            for name, value in zip(fetch, spec):
                key[name[2:]] = value

        return key

    def update(self, data):
        for key, value in data.items():
            self.load_value(key, value)

    def load_value(self, key, value):
        if key not in self.changed:
            dict.__setitem__(self, key, value)

    def load_sql(self):
        keys = []
        values = []
        for name, value in self.key.items():
            keys.append('f_%s = ?' % name)
            values.append(value)
        spec = (self
                .db
                .execute('SELECT * FROM %s WHERE %s' %
                         (self.table, ' AND '.join(keys)), values)
                .fetchone())
        self.update(dict(zip(self.names, spec)))
        return self

    def load_rtnlmsg(self, target, event):
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
                self.load_value(self.iclass.nla2name(name), value)
