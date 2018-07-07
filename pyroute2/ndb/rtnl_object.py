import time
import weakref
import threading


class RTNL_Object(dict):

    table = None   # model table -- always one of the main tables
    view = None    # (optional) view to load values for the summary etc.
    etable = None  # effective table -- may be a snapshot

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
        self.nl = view.ndb.nl
        self.ctxid = ctxid or id(self)
        self.schema = view.ndb.schema
        self.changed = set()
        self.iclass = iclass
        self.etable = self.table
        self.errors = []
        self.load_event = threading.Event()
        self.kspec = ('target', ) + self.schema.indices[self.table]
        self.spec = self.schema.compiled[self.table]['all_names']
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
        snp = type(self)(self.view, self.key, ctxid)
        self.schema.save_deps(snp.ctxid, weakref.ref(snp))
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

    def rollback(self, snapshot=None):
        snapshot = snapshot or self.last_save
        snapshot.scope = self.scope
        snapshot.next_scope = 'system'
        snapshot.apply(rollback=True)

    def commit(self):
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

    def check(self):
        self.load_sql()

        if self.next_scope and self.scope != self.next_scope:
            return False

        if self.changed:
            return False

        return True

    def apply(self, rollback=False):

        self.load_event.clear()

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
        self.load_sql(set_scope=False)
        scope = self.scope

        # Create the request.
        idx_req = dict([(x, self[self.iclass.nla2name(x)]) for x in
                        self.schema.compiled[self.table]['idx']])
        req = dict(idx_req)
        for key in self.changed:
            req[key] = self[key]
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
            for table in self.schema.spec:
                if table == self.table:
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
        elif self[key] == value:
            self.changed.remove(key)

    def load_sql(self, ctxid=None, set_scope=True):
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
