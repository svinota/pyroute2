import time
import uuid
import struct
import threading
import traceback
from functools import partial
from collections import OrderedDict
from socket import (AF_INET,
                    inet_pton)
from pyroute2 import config
from pyroute2.common import uuid32
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh


def db_lock(method):
    def f(self, *argv, **kwarg):
        with self.db_lock:
            return method(self, *argv, **kwarg)
    return f


class DBSchema(object):

    connection = None
    thread = None
    event_map = None
    key_defaults = None
    snapshots = None  # <table_name>: <obj_weakref>

    spec = {'interfaces': OrderedDict(ifinfmsg.sql_schema()),
            'addresses': OrderedDict(ifaddrmsg.sql_schema()),
            'neighbours': OrderedDict(ndmsg.sql_schema()),
            'routes': OrderedDict(rtmsg.sql_schema() +
                                  [('route_id', 'TEXT UNIQUE'),
                                   ('gc_mark', 'INTEGER')]),
            'nh': OrderedDict(nh.sql_schema() +
                              [('route_id', 'TEXT'),
                               ('nh_id', 'INTEGER')])}

    classes = {'interfaces': ifinfmsg,
               'addresses': ifaddrmsg,
               'neighbours': ndmsg,
               'routes': rtmsg}

    #
    # OBS: field names MUST go in the same order as in the spec,
    # that's for the load_netlink() to work correctly -- it uses
    # one loop to fetch both index and row values
    #
    indices = {'interfaces': ('index', ),
               'addresses': ('index',
                             'IFA_ADDRESS',
                             'IFA_LOCAL'),
               'neighbours': ('ifindex',
                              'NDA_LLADDR'),
               'routes': ('family',
                          'dst_len',
                          'tos',
                          'RTA_DST',
                          'RTA_PRIORITY',
                          'RTA_TABLE'),
               'nh': ('route_id',
                      'nh_id')}

    foreign_keys = {'addresses': [{'fields': ('f_target',
                                              'f_tflags',
                                              'f_index'),
                                   'parent_fields': ('f_target',
                                                     'f_tflags',
                                                     'f_index'),
                                   'parent': 'interfaces'}],
                    'neighbours': [{'fields': ('f_target',
                                               'f_tflags',
                                               'f_ifindex'),
                                    'parent_fields': ('f_target',
                                                      'f_tflags',
                                                      'f_index'),
                                    'parent': 'interfaces'}],
                    'routes': [{'fields': ('f_target',
                                           'f_tflags',
                                           'f_RTA_OIF'),
                                'parent_fields': ('f_target',
                                                  'f_tflags',
                                                  'f_index'),
                                'parent': 'interfaces'},
                               {'fields': ('f_target',
                                           'f_tflags',
                                           'f_RTA_IIF'),
                                'parent_fields': ('f_target',
                                                  'f_tflags',
                                                  'f_index'),
                                'parent': 'interfaces'}],
                    #
                    # man kan not use f_tflags together with f_route_id
                    # 'cause it breaks ON UPDATE CASCADE for interfaces
                    #
                    'nh': [{'fields': ('f_route_id', ),
                            'parent_fields': ('f_route_id', ),
                            'parent': 'routes'},
                           {'fields': ('f_target',
                                       'f_tflags',
                                       'f_oif'),
                            'parent_fields': ('f_target',
                                              'f_tflags',
                                              'f_index'),
                            'parent': 'interfaces'}]}

    def __init__(self, connection, mode, rtnl_log, tid):
        self.mode = mode
        self.thread = tid
        self.connection = connection
        self.rtnl_log = rtnl_log
        self.snapshots = {}
        self.key_defaults = {}
        self.db_lock = threading.RLock()
        self._cursor = None
        self._counter = 0
        self.share_cursor()
        if self.mode == 'sqlite3':
            # SQLite3
            self.connection.execute('PRAGMA foreign_keys = ON')
            self.plch = '?'
        elif self.mode == 'psycopg2':
            # PostgreSQL
            self.plch = '%s'
        else:
            raise NotImplementedError('database provider not supported')
        self.gctime = self.ctime = time.time()
        for table in ('interfaces',
                      'addresses',
                      'neighbours',
                      'routes',
                      'nh'):
            self.create_table(table)
        #
        # compile request lines
        #
        self.compiled = {}
        tables = self.spec.keys()
        for table in tables:
            names = ('target', 'tflags') + tuple(self.spec[table].keys())
            fnames = ['f_%s' % x for x in names]
            fset = ['f_%s = %s' % (x, self.plch) for x in names]
            plchs = [self.plch] * len(fnames)
            idx = ('target', 'tflags') + self.indices[table]
            knames = ['f_%s' % x for x in idx]
            fidx = ['%s.%s = %s' % (table, x, self.plch) for x in knames]
            self.compiled[table] = {'names': names,
                                    'idx': idx,
                                    'fnames': ','.join(fnames),
                                    'plchs': ','.join(plchs),
                                    'fset': ','.join(fset),
                                    'knames': ','.join(knames),
                                    'fidx': ' AND '.join(fidx)}

        #
        # specific SQL code
        #
        if self.mode == 'sqlite3':
            self.execute('''
                         CREATE TRIGGER IF NOT EXISTS nh_f_tflags
                         BEFORE UPDATE OF f_tflags ON nh FOR EACH ROW
                             BEGIN
                                 UPDATE routes
                                 SET f_tflags = NEW.f_tflags
                                 WHERE f_route_id = NEW.f_route_id;
                             END
                         ''')
        elif self.mode == 'psycopg2':
            self.execute('''
                         CREATE OR REPLACE FUNCTION nh_f_tflags()
                         RETURNS trigger AS $nh_f_tflags$
                             BEGIN
                                 UPDATE routes
                                 SET f_tflags = NEW.f_tflags
                                 WHERE f_route_id = NEW.f_route_id;
                                 RETURN NEW;
                             END;
                         $nh_f_tflags$ LANGUAGE plpgsql;

                         DROP TRIGGER IF EXISTS nh_f_tflags ON nh;

                         CREATE TRIGGER nh_f_tflags
                         BEFORE UPDATE OF f_tflags ON nh FOR EACH ROW
                         EXECUTE PROCEDURE nh_f_tflags();
                         ''')

    @db_lock
    def execute(self, *argv, **kwarg):
        if self._cursor:
            cursor = self._cursor
        else:
            cursor = self.connection.cursor()
            self._counter = config.db_transaction_limit + 1
        try:
            cursor.execute(*argv, **kwarg)
        finally:
            if self._counter > config.db_transaction_limit:
                self.connection.commit()  # no performance optimisation yet
                self._counter = 0
        return cursor

    @db_lock
    def share_cursor(self):
        self._cursor = self.connection.cursor()
        self._counter = 0

    @db_lock
    def unshare_cursor(self):
        self._cursor = None
        self._counter = 0
        self.connection.commit()

    @db_lock
    def close(self):
        self.purge_snapshots()
        self.connection.commit()
        self.connection.close()

    @db_lock
    def commit(self):
        return self.connection.commit()

    @db_lock
    def create_table(self, table):
        req = ['f_target TEXT NOT NULL',
               'f_tflags BIGINT NOT NULL DEFAULT 0']
        fields = []
        self.key_defaults[table] = {}
        for field in self.spec[table].items():
            #
            # Why f_?
            # 'Cause there are attributes like 'index' and such
            # names may not be used in SQL statements
            #
            fields.append('f_%s %s' % field)
            req.append('f_%s %s' % field)
            if field[1].strip().startswith('TEXT'):
                self.key_defaults[table][field[0]] = ''
            else:
                self.key_defaults[table][field[0]] = 0
        if table in self.foreign_keys:
            for key in self.foreign_keys[table]:
                spec = ('(%s)' % ','.join(key['fields']),
                        '%s(%s)' % (key['parent'],
                                    ','.join(key['parent_fields'])))
                req.append('FOREIGN KEY %s REFERENCES %s '
                           'ON UPDATE CASCADE '
                           'ON DELETE CASCADE ' % spec)
                #
                # make a unique index for compound keys on
                # the parent table
                #
                # https://sqlite.org/foreignkeys.html
                #
                if len(key['fields']) > 1:
                    idxname = 'uidx_%s_%s' % (key['parent'],
                                              '_'.join(key['parent_fields']))
                    self.execute('CREATE UNIQUE INDEX '
                                 'IF NOT EXISTS %s ON %s' %
                                 (idxname, spec[1]))

        req = ','.join(req)
        req = ('CREATE TABLE IF NOT EXISTS '
               '%s (%s)' % (table, req))
        self.execute(req)

        index = ','.join(['f_target', 'f_tflags'] + ['f_%s' % x for x
                                                     in self.indices[table]])
        req = ('CREATE UNIQUE INDEX IF NOT EXISTS '
               '%s_idx ON %s (%s)' % (table, table, index))
        self.execute(req)

        #
        # create table for the transaction buffer: there go the system
        # updates while the transaction is not committed.
        #
        # w/o keys (yet)
        #
        # req = ['f_target TEXT NOT NULL',
        #        'f_tflags INTEGER NOT NULL DEFAULT 0']
        # req = ','.join(req)
        # self.execute('CREATE TABLE IF NOT EXISTS '
        #              '%s_buffer (%s)' % (table, req))
        #
        # create the log table, if required
        #
        if self.rtnl_log:
            req = ['f_tstamp BIGINT NOT NULL',
                   'f_target TEXT NOT NULL'] + fields
            req = ','.join(req)
            self.execute('CREATE TABLE IF NOT EXISTS '
                         '%s_log (%s)' % (table, req))

    @db_lock
    def save_deps(self, objid, wref):
        uuid = uuid32()
        obj = wref()
        idx = self.indices[obj.table]
        conditions = []
        values = []
        for key in idx:
            conditions.append('f_%s = %s' % (key, self.plch))
            values.append(obj.get(self.classes[obj.table].nla2name(key)))
        #
        # save the old f_tflags value
        #
        tflags = self.execute('''
                              SELECT f_tflags FROM %s
                              WHERE %s
                              '''
                              % (obj.table,
                                 ' AND '.join(conditions)),
                              values).fetchone()[0]
        #
        # mark tflags for obj
        #
        self.execute('''
                     UPDATE %s SET
                         f_tflags = %s
                     WHERE %s
                     '''
                     % (obj.table,
                        self.plch,
                        ' AND '.join(conditions)),
                     [uuid] + values)
        #
        # t_flags is used in foreign keys ON UPDATE CASCADE, so all
        # related records will be marked, now just copy the marked data
        #
        for table in self.spec:
            #
            # create the snapshot table
            #
            self.execute('''
                         CREATE TABLE IF NOT EXISTS %s_%s
                         AS SELECT * FROM %s
                         WHERE
                             f_tflags IS NULL
                         '''
                         % (table, objid, table))
            #
            # copy the data -- is it possible to do it in one step?
            #
            self.execute('''
                         INSERT INTO %s_%s
                         SELECT * FROM %s
                         WHERE
                             f_tflags = %s
                         '''
                         % (table, objid, table, self.plch),
                         [uuid])
        #
        # unmark all the data
        #
        self.execute('''
                     UPDATE %s SET
                         f_tflags = %s
                     WHERE %s
                     '''
                     % (obj.table,
                        self.plch,
                        ' AND '.join(conditions)),
                     [tflags] + values)
        for table in self.spec:
            self.execute('''
                         UPDATE %s_%s SET f_tflags = %s
                         ''' % (table, objid, self.plch),
                         [tflags])
            self.snapshots['%s_%s' % (table, objid)] = wref

    @db_lock
    def purge_snapshots(self):
        for table in tuple(self.snapshots):
            self.execute('DROP TABLE %s' % table)
            del self.snapshots[table]

    @db_lock
    def get(self, table, spec):
        #
        # Retrieve info from the DB
        #
        # ndb.interfaces.get({'ifname': 'eth0'})
        #
        conditions = []
        values = []
        ret = []
        cls = self.classes[table]
        for key, value in spec.items():
            if key not in [x[0] for x in cls.fields]:
                key = cls.name2nla(key)
            conditions.append('f_%s = %s' % (key, self.plch))
            values.append(value)
        req = 'SELECT * FROM %s WHERE %s' % (table, ' AND '.join(conditions))
        for record in self.execute(req, values).fetchall():
            ret.append(dict(zip(self.spec[table].keys(), record)))
        return ret

    @db_lock
    def rtmsg_gc_mark(self, target, event, gc_mark=None):
        #
        if gc_mark is None:
            gc_clause = ' AND f_gc_mark IS NOT NULL'
        else:
            gc_clause = ''
        #
        # select all routes for that OIF where f_gc_mark is not null
        #
        key_fields = ','.join(['f_%s' % x for x
                               in self.indices['routes']])
        key_query = ' AND '.join(['f_%s = %s' % (x, self.plch) for x
                                  in self.indices['routes']])
        routes = (self
                  .execute('SELECT %s,f_RTA_GATEWAY FROM routes WHERE '
                           'f_target = %s AND f_RTA_OIF = %s AND '
                           'f_RTA_GATEWAY IS NOT NULL %s'
                           % (key_fields, self.plch, self.plch, gc_clause),
                           (target, event.get_attr('RTA_OIF')))
                  .fetchall())
        #
        # get the route's RTA_DST and calculate the network
        #
        addr = event.get_attr('RTA_DST')
        net = struct.unpack('>I', inet_pton(AF_INET, addr))[0] &\
            (0xffffffff << (32 - event['dst_len']))
        #
        # now iterate all the routes from the query above and
        # mark those with matching RTA_GATEWAY
        #
        for route in routes:
            # get route GW
            gw = route[-1]
            gwnet = struct.unpack('>I', inet_pton(AF_INET, gw))[0] & net
            if gwnet == net:
                (self
                 .execute('UPDATE routes SET f_gc_mark = %s '
                          'WHERE f_target = %s AND %s'
                          % (self.plch, self.plch, key_query),
                          (gc_mark, target) + route[:-1]))

    @db_lock
    def load_ifinfmsg(self, target, event):
        #
        # link goes down: flush all related routes
        #
        if not event['flags'] & 1:
            self.execute('DELETE FROM routes WHERE '
                         'f_RTA_OIF = %s OR f_RTA_IIF = %s'
                         % (self.plch, self.plch),
                         (event['index'], event['index']))
        #
        # ignore wireless updates
        #
        if event.get_attr('IFLA_WIRELESS'):
            return
        #
        # continue with load_netlink()
        self.load_netlink('interfaces', target, event)

    @db_lock
    def load_rtmsg(self, target, event):
        mp = event.get_attr('RTA_MULTIPATH')

        # create an mp route
        if (not event['header']['type'] % 2) and mp:
            #
            # create key
            keys = ['f_target = %s' % self.plch]
            values = [target]
            for key in self.indices['routes']:
                keys.append('f_%s = %s' % (key, self.plch))
                values.append(event.get(key) or event.get_attr(key))
            #
            spec = 'WHERE %s' % ' AND '.join(keys)
            s_req = 'SELECT f_route_id FROM routes %s' % spec
            #
            # get existing route_id
            route_id = self.execute(s_req, values).fetchall()
            if route_id:
                #
                # if exists
                route_id = route_id[0][0]
                #
                # flush all previous MP hops
                d_req = 'DELETE FROM nh WHERE f_route_id= %s' % self.plch
                self.execute(d_req, (route_id, ))
            else:
                #
                # or create a new route_id
                route_id = str(uuid.uuid4())
            #
            # set route_id on the route itself
            event['route_id'] = route_id
            self.load_netlink('routes', target, event)
            for idx in range(len(mp)):
                mp[idx]['header'] = {}          # for load_netlink()
                mp[idx]['route_id'] = route_id  # set route_id on NH
                mp[idx]['nh_id'] = idx          # add NH number
                self.load_netlink('nh', target, mp[idx], 'routes')
            #
            # we're done with an MP-route, just exit
            return
        #
        # manage gc marks on related routes
        #
        # only for automatic routes:
        #   - table 254 (main)
        #   - proto 2 (kernel)
        #   - scope 253 (link)
        elif (event.get_attr('RTA_TABLE') == 254) and \
                (event['proto'] == 2) and \
                (event['scope'] == 253) and \
                (event['family'] == AF_INET):
            evt = event['header']['type']
            #
            # set f_gc_mark = timestamp for "del" events
            # and clean it for "new" events
            #
            self.rtmsg_gc_mark(target, event,
                               int(time.time()) if (evt % 2) else None)
            #
            # continue with load_netlink()
            #
        #
        # ... or work on a regular route
        self.load_netlink("routes", target, event)

    @db_lock
    def log_netlink(self, table, target, event, ctable=None):
        #
        # RTNL Logs
        #
        fkeys = tuple(self.spec[table].keys())
        fields = ','.join(['f_tstamp', 'f_target'] +
                          ['f_%s' % x for x in fkeys])
        pch = ','.join([self.plch] * (len(fkeys) + 2))
        values = [int(time.time() * 1000), target]
        for field in fkeys:
            value = event.get_attr(field) or event.get(field)
            if value is None and field in self.indices[ctable or table]:
                value = self.key_defaults[table][field]
            values.append(value)
        self.execute('INSERT INTO %s_log (%s) VALUES (%s)'
                     % (table, fields, pch), values)

    @db_lock
    def load_netlink(self, table, target, event, ctable=None):
        #
        # Simple barrier to work with the DB only from
        # one thread
        #
        # ? make a decorator ?
        if self.thread != id(threading.current_thread()):
            return
        #
        # Periodic jobs
        #
        if time.time() - self.gctime > config.gc_timeout:
            self.gctime = time.time()

            # clean dead snapshots after GC timeout
            for name, wref in self.snapshots.items():
                if wref() is None:
                    del self.snapshots[name]
                    self.execute('DROP TABLE %s' % name)

            # clean marked routes
            self.execute('DELETE FROM routes WHERE '
                         '(f_gc_mark + 5) < %s' % self.plch,
                         (int(time.time()), ))
        #
        # The event type
        #
        if event['header'].get('type', 0) % 2:
            #
            # Delete an object
            #
            conditions = ['f_target = %s' % self.plch]
            values = [target]
            for key in self.indices[table]:
                conditions.append('f_%s = %s' % (key, self.plch))
                value = event.get(key) or event.get_attr(key)
                if value is None:
                    value = self.key_defaults[table][key]
                values.append(value)
            self.execute('DELETE FROM %s WHERE'
                         ' %s' % (table, ' AND '.join(conditions)), values)
        else:
            #
            # Create or set an object
            #
            # field values
            values = [target, 0]
            # index values
            ivalues = [target, 0]
            compiled = self.compiled[table]

            # fetch values (exc. the first two columns)
            for field in compiled['names'][len(values):]:
                # NLA have priority
                value = event.get_attr(field) or event.get(field)
                if value is None and \
                        field in self.compiled[ctable or table]['idx']:
                    value = self.key_defaults[table][field]
                if field in compiled['idx']:
                    ivalues.append(value)
                values.append(value)

            try:
                if self.mode == 'psycopg2':
                    #
                    # run UPSERT -- the DB provider must support it
                    #
                    (self
                     .execute('INSERT INTO %s (%s) VALUES (%s) '
                              'ON CONFLICT (%s) '
                              'DO UPDATE SET %s WHERE %s'
                              % (table,
                                 compiled['fnames'],
                                 compiled['plchs'],
                                 compiled['knames'],
                                 compiled['fset'],
                                 compiled['fidx']),
                              (values + values + ivalues)))
                    #
                elif self.mode == 'sqlite3':
                    #
                    # SQLite3 >= 3.24 actually has UPSERT, but ...
                    #
                    self.execute('INSERT OR REPLACE INTO %s (%s) VALUES (%s)'
                                 % (table,
                                    compiled['fnames'],
                                    compiled['plchs']), values)
                else:
                    raise NotImplementedError()
                #
            except Exception:
                #
                # A good question, what should we do here
                traceback.print_exc()


def init(connection, mode, rtnl_log, tid):
    ret = DBSchema(connection, mode, rtnl_log, tid)
    ret.event_map = {ifinfmsg: [ret.load_ifinfmsg],
                     ifaddrmsg: [partial(ret.load_netlink, 'addresses')],
                     ndmsg: [partial(ret.load_netlink, 'neighbours')],
                     rtmsg: [ret.load_rtmsg]}
    if rtnl_log:
        types = dict([(x[1], x[0]) for x in ret.classes.items()])
        for msg_type, handlers in ret.event_map.items():
            handlers.append(partial(ret.log_netlink, types[msg_type]))
    return ret
