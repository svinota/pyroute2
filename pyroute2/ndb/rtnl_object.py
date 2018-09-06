import time
import weakref
import threading


class RTNL_Object(dict):

    table = None   # model table -- always one of the main tables
    view = None    # (optional) view to load values for the summary etc.
    etable = None  # effective table -- may be a snapshot
    utable = None  # table to send updates to

    key = None
    key_extra_fields = []

    schema = None
    event_map = None
    scope = None
    next_scope = None
    summary = None
    summary_header = None
    dump = None
    dump_header = None
    dump_pre = []
    dump_post = []
    errors = None
    msg_class = None

    def __init__(self, view, key, iclass, ctxid=None):
        self.view = view
        self.sources = view.ndb.sources
        self.ctxid = ctxid or id(self)
        self.schema = view.ndb.schema
        self.changed = set()
        self.iclass = iclass
        self.etable = self.table
        self.utable = self.utable or self.table
        self.errors = []
        self.snapshot_deps = []
        self.load_event = threading.Event()
        self.kspec = ('target', ) + self.schema.indices[self.table]
        self.spec = self.schema.compiled[self.table]['all_names']
        self.names = self.schema.compiled[self.table]['norm_names']
        create = key.pop('create', False) if isinstance(key, dict) else False
        ckey = self.complete_key(key)
        if create and ckey is not None:
            raise KeyError('object exists')
        elif not create and ckey is None:
            raise KeyError('object does not exists')
        elif create:
            for name in key:
                self[name] = key[name]
            self.scope = 'invalid'
            # FIXME -- merge with complete_key()
            if 'target' not in self:
                self.load_value('target', 'localhost')
        else:
            self.key = ckey
            self.load_sql()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.commit()

    def __hash__(self):
        return id(self)

    def __setitem__(self, key, value):
        if value != self.get(key, None):
            self.changed.add(key)
            dict.__setitem__(self, key, value)

    @property
    def key(self):
        ret = {}
        for name in self.kspec:
            kname = self.iclass.nla2name(name)
            if self.get(kname):
                ret[name] = self[kname]
        if len(ret) < len(self.kspec):
            for name in self.key_extra_fields:
                kname = self.iclass.nla2name(name)
                if self.get(kname):
                    ret[name] = self[kname]
        return ret

    @key.setter
    def key(self, k):
        if not isinstance(k, dict):
            return
        for key, value in k.items():
            if value is not None:
                dict.__setitem__(self, self.iclass.nla2name(key), value)

    def snapshot(self, ctxid=None):
        snp = type(self)(self.view, self.key, ctxid)
        self.schema.save_deps(snp.ctxid, weakref.ref(snp), self.iclass)
        snp.etable = '%s_%s' % (snp.table, snp.ctxid)
        snp.changed = set(self.changed)
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
                if name not in self.spec:
                    name = self.iclass.name2nla(name)
                if name in self.spec:
                    keys.append('f_%s = %s' % (name, self.schema.plch))
                    values.append(value)
            with self.schema.db_lock:
                spec = (self
                        .schema
                        .execute('SELECT %s FROM %s WHERE %s' %
                                 (' , '.join(fetch),
                                  self.etable,
                                  ' AND '.join(keys)),
                                 values)
                        .fetchone())
            if spec is None:
                return None
            for name, value in zip(fetch, spec):
                key[name[2:]] = value

        return key

    def rollback(self, snapshot=None):
        snapshot = snapshot or self.last_save
        snapshot.scope = self.scope
        snapshot.next_scope = 'system'
        snapshot.apply(rollback=True)
        for link, snp in snapshot.snapshot_deps:
            link.rollback(snapshot=snp)

    def commit(self):
        # Is it a new object?
        if self.scope == 'invalid':
            # Save values, try to apply
            save = dict(self)
            try:
                return self.apply()
            except Exception as e_i:
                # ACHTUNG! The routine doesn't clean up the system
                #
                # Drop all the values and rollback to the initial state
                for key in tuple(self.keys()):
                    del self[key]
                for key in save:
                    dict.__setitem__(self, key, save[key])
                raise e_i

        # Continue with an existing object

        # Save the context
        self.last_save = self.snapshot()

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
                self.rollback()
            except Exception as e_r:
                e_c.chain = [e_r]
                if hasattr(e_r, 'chain'):
                    e_c.chain.extend(e_r.chain)
                e_r.chain = None
            raise
        return self

    def remove(self):
        self.scope = 'remove'
        self.next_scope = 'invalid'
        return self

    def check(self):
        self.load_sql()

        if self.next_scope and self.scope != self.next_scope:
            return False

        if self.changed:
            return False

        return True

    def make_req(self, scope, prime):
        req = dict(prime)
        for key in self.changed:
            req[key] = self[key]
        return req

    def get_scope(self):
        conditions = []
        values = []
        for name in self.kspec:
            conditions.append('f_%s = %s' % (name, self.schema.plch))
            values.append(self.get(self.iclass.nla2name(name), None))
        return (self
                .schema
                .fetchone('''
                          SELECT count(*) FROM %s WHERE %s
                          ''' % (self.table,
                                 ' AND '.join(conditions)),
                          values)[0])

    def apply(self, rollback=False):

        self.load_event.clear()

        # Get the API entry point. The RTNL source must comply to the
        # IPRoute API.
        #
        # self.sources = {'localhost': Source(),
        #                 'remote': ...}
        #
        # self.api = 'link'
        # Source().nl -- RTNL API
        #
        # -> api(...) = iproute.link(...)
        #
        api = getattr(self.sources[self['target']].nl, self.api)

        # Load the current state
        self.schema.connection.commit()
        self.load_sql(set_scope=False)
        if self.get_scope() == 0:
            scope = 'invalid'
        else:
            scope = self.scope

        # Create the request.
        idx_req = dict([(x, self[self.iclass.nla2name(x)]) for x
                        in self.schema.compiled[self.table]['idx']
                        if self.iclass.nla2name(x) in self])
        req = self.make_req(scope, idx_req)

        #
        if scope == 'invalid':
            api('add', **dict([x for x in self.items() if x[1] is not None]))
        elif scope == 'system':
            api('set', **req)
        elif scope == 'remove':
            api('del', **idx_req)

        for _ in range(3):
            if self.check():
                break
            self.load_event.wait(1)
            self.load_event.clear()
        else:
            raise Exception('timeout while applying changes')

        #
        if rollback:
            #
            # Iterate all the snapshot tables and collect the diff
            for (table, cls) in self.view.classes.items():
                if issubclass(type(self), cls) or \
                        issubclass(cls, type(self)):
                    continue
                # comprare the tables
                diff = (self
                        .schema
                        .fetch('''
                               SELECT * FROM %s_%s
                                   EXCEPT
                               SELECT * FROM %s
                               '''
                               % (table, self.ctxid, table)))
                for record in diff:
                    record = dict(zip((self
                                       .schema
                                       .compiled[table]['all_names']),
                                      record))
                    key = dict([x for x in record.items()
                                if x[0] in self.schema.compiled[table]['idx']])
                    obj = self.view.get(key, table)
                    obj.load_sql(ctxid=self.ctxid)
                    obj.scope = 'invalid'
                    obj.next_scope = 'system'
                    try:
                        obj.apply()
                    except Exception as e:
                        self.errors.append((time.time(), obj, e))

    def update(self, data):
        for key, value in data.items():
            self.load_value(key, value)

    def load_value(self, key, value):
        if key not in self.changed:
            dict.__setitem__(self, key, value)
        elif self.get(key) == value:
            self.changed.remove(key)

    def load_sql(self, ctxid=None, set_scope=True):

        if not self.key:
            return

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
                .fetchone('SELECT * FROM %s WHERE %s' %
                          (table, ' AND '.join(keys)), values))
        if set_scope:
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

        if event['header'].get('type', 0) % 2:
            self.scope = 'invalid'
            self.changed = set()
        else:
            self.load_sql()
        self.load_event.set()
