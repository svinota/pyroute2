import weakref


class RTNL_Object(dict):

    table = None
    schema = None
    event_map = None
    scope = None
    summary = None
    summary_header = None
    dump = None
    dump_header = None
    dump_pre = []
    dump_post = []

    def __init__(self, schema, nl, key, iclass, ctxid=None):
        self.nl = nl
        self.ctxid = ctxid or id(self)
        self.schema = schema
        self.changed = set()
        self.iclass = iclass
        self.etable = self.table
        self.kspec = ('target', ) + schema.indices[self.table]
        self.spec = schema.compiled[self.table]['anames']
        self.names = tuple((iclass.nla2name(x) for x in self.spec))
        self.key = self.complete_key(key)
        self.load_sql()

    def __hash__(self):
        return id(self)

    def __setitem__(self, key, value):
        if value != self.get(key, None):
            self.changed.add(key)
            dict.__setitem__(self, key, value)

    def snapshot(self, ctxid=None):
        snp = type(self)(self.schema, self.nl, self.key, ctxid)
        self.schema.save_deps(snp.ctxid, weakref.ref(snp))
        snp.etable = '%s_%s' % (snp.table, snp.ctxid)
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
                keys.append('f_%s = %s' % (name, self.schema.plch))
                values.append(value)
            spec = (self
                    .schema
                    .execute('SELECT %s FROM %s WHERE %s' %
                             (' , '.join(fetch),
                              self.etable,
                              ' AND '.join(keys)),
                             values)
                    .fetchone())
            for name, value in zip(fetch, spec):
                key[name[2:]] = value

        return key

    def commit(self):
        # Save the context
        snapshot = self.snapshot()

        # The snapshot tables in the DB will be dropped as soon as the GC
        # collects the object. But in the case of an exception the `snp`
        # variable will be saved in the traceback, so the tables will be
        # available to debug. If the traceback will be saved somewhere then
        # the tables will never be dropped by the GC, so you can do it
        # manually by `ndb.schema.purge_snapshots()` -- to invalidate all
        # the snapshots and to drop the associated tables.

        # Apply the changes
        try:
            self.apply()
        except Exception as e_c:
            # Rollback in the case of any error
            try:
                self.load_sql()
                snapshot.apply(scope=self.scope)
            except Exception as e_r:
                e_c.chain = [e_r]
                if hasattr(e_r, 'chain'):
                    e_c.chain.extend(e_r.chain)
                e_r.chain = None
            raise

    def remove(self):
        self.scope = 'remove'

    def apply(self, scope=None):

        # Get the API entry point. The RTNL source must comply to the
        # IPRoute API.
        #
        # self.nl = {'localhost': IPRoute(),
        #            'remote': ...}
        #
        # self.api = 'link'
        #
        # -> api(...) = iproute.link(...)
        #
        api = getattr(self.nl[self['target']], self.api)

        # Load the current state
        if self.scope != 'remove':
            self.load_sql()
        scope = scope or self.scope

        # Create the request.
        idx_req = dict([(x, self[self.iclass.nla2name(x)]) for x in
                        self.schema.compiled[self.table]['idx']])
        req = dict(idx_req)
        for key in self.changed:
            req[key] = self[key]
        #
        if scope == 'invalid':
            api('add', **self)
        elif scope == 'system':
            api('set', **req)
        elif scope == 'remove':
            api('del', **idx_req)

    def update(self, data):
        for key, value in data.items():
            self.load_value(key, value)

    def load_value(self, key, value):
        if key not in self.changed:
            dict.__setitem__(self, key, value)

    def load_sql(self, ctxid=None):
        if ctxid is None:
            table = self.etable
        else:
            table = '%s_%s' % (self.table, ctxid)
        keys = []
        values = []
        for name, value in self.key.items():
            keys.append('f_%s = %s' % (name, self.schema.plch))
            values.append(value)
        spec = (self
                .schema
                .execute('SELECT * FROM %s WHERE %s' %
                         (table, ' AND '.join(keys)), values)
                .fetchone())
        if spec is None:
            # No such object (anymore)
            self.scope = 'invalid'
        else:
            self.update(dict(zip(self.names, spec)))
            self.scope = 'system'

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
        for name in self.spec:
            value = event.get_attr(name) or event.get(name)
            if value is not None:
                self.load_value(self.iclass.nla2name(name), value)
