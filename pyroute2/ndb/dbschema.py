import time
import uuid
import struct
import sqlite3
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
    indices = {'interfaces': ('index',
                              'IFLA_IFNAME'),
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

    foreign_keys = {'addresses': [{'cols': ('f_target',
                                            'f_tflags',
                                            'f_index'),
                                   'pcls': ('f_target',
                                            'f_tflags',
                                            'f_index'),
                                   'parent': 'interfaces'}],
                    'neighbours': [{'cols': ('f_target',
                                             'f_tflags',
                                             'f_ifindex'),
                                    'pcls': ('f_target',
                                             'f_tflags',
                                             'f_index'),
                                    'parent': 'interfaces'}],
                    'routes': [{'cols': ('f_target',
                                         'f_tflags',
                                         'f_RTA_OIF'),
                                'pcls': ('f_target',
                                         'f_tflags',
                                         'f_index'),
                                'parent': 'interfaces'},
                               {'cols': ('f_target',
                                         'f_tflags',
                                         'f_RTA_IIF'),
                                'pcls': ('f_target',
                                         'f_tflags',
                                         'f_index'),
                                'parent': 'interfaces'}],
                    #
                    # man kan not use f_tflags together with f_route_id
                    # 'cause it breaks ON UPDATE CASCADE for interfaces
                    #
                    'nh': [{'cols': ('f_route_id', ),
                            'pcls': ('f_route_id', ),
                            'parent': 'routes'},
                           {'cols': ('f_target',
                                     'f_tflags',
                                     'f_oif'),
                            'pcls': ('f_target',
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
        # specific SQL code
        #
        self.execute('''
                     CREATE TRIGGER IF NOT EXISTS nh_f_tflags
                     BEFORE UPDATE OF f_tflags ON nh FOR EACH ROW
                     BEGIN
                         UPDATE routes
                         SET f_tflags = NEW.f_tflags
                         WHERE f_route_id = NEW.f_route_id ;
                     END
                     ''')

    def execute(self, *argv, **kwarg):
        cursor = self.connection.cursor()
        try:
            cursor.execute(*argv, **kwarg)
        finally:
            self.connection.commit()  # no performance optimisation yet
        return cursor

    def close(self):
        return self.connection.close()

    def commit(self):
        return self.connection.commit()

    def create_table(self, table):
        req = ['f_target TEXT NOT NULL',
               'f_tflags INTEGER NOT NULL DEFAULT 0']
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
                spec = ('(%s)' % ','.join(key['cols']),
                        '%s(%s)' % (key['parent'], ','.join(key['pcls'])))
                req.append('FOREIGN KEY %s REFERENCES %s '
                           'ON UPDATE CASCADE '
                           'ON DELETE CASCADE ' % spec)
                #
                # make a unique index for compound keys on
                # the parent table
                #
                # https://sqlite.org/foreignkeys.html
                #
                if len(key['cols']) > 1:
                    idxname = 'uidx_%s_%s' % (key['parent'],
                                              '_'.join(key['pcls']))
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
            req = ['f_tstamp INTEGER NOT NULL',
                   'f_target TEXT NOT NULL'] + fields
            req = ','.join(req)
            self.execute('CREATE TABLE IF NOT EXISTS '
                         '%s_log (%s)' % (table, req))

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
        # mark tflags for obj
        #
        self.execute('UPDATE %s SET f_tflags = %s WHERE %s'
                     % (obj.table, self.plch, ' AND '.join(conditions)),
                     [uuid] + values)
        #
        # t_flags is used in foreign keys ON UPDATE CASCADE, so all
        # related records will be marked, now just copy the marked data
        #
        for table in self.spec:
            self.execute('CREATE TABLE %s_%s AS SELECT * FROM %s '
                         'WHERE f_tflags = %s'
                         % (table, objid, table, self.plch),
                         [uuid])
        #
        # unmark all the data
        #
        self.execute('UPDATE %s SET f_tflags = 0 WHERE %s'
                     % (obj.table, ' AND '.join(conditions)),
                     values)
        for table in self.spec:
            self.execute('UPDATE %s_%s SET f_tflags = 0' % (table, objid))
            self.snapshots['%s_%s' % (table, objid)] = wref

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
            # table spec
            spec = ('target', 'tflags') + tuple(self.spec[table].keys())
            # index spec
            ispec = ('target', 'tflags') + self.indices[table]
            # reference table index spec
            cspec = ('target', 'tflags') + self.indices[ctable or table]
            # field values
            values = [target, 0]
            # index values
            ivalues = [target, 0]

            # fetch values (exc. the first two columns)
            for field in spec[len(values):]:
                # NLA have priority
                value = event.get_attr(field) or event.get(field)
                if value is None and field in cspec:
                    value = self.key_defaults[table][field]
                if field in ispec:
                    ivalues.append(value)
                values.append(value)

            # 1. generate field names list
            fnames = ','.join(['f_%s' % x
                               for x in spec])
            # 2. generage placeholders list
            plchls = ','.join([self.plch] * len(spec))
            # 3. generate set equations list
            setlst = ','.join(['f_%s = %s' % (x, self.plch)
                               for x in spec])
            # 4. generate index conditions
            idxlst = ' AND '.join(['%s.f_%s = %s' % (table, x, self.plch)
                                   for x in ispec])
            # 5. generate index field names list
            knames = ','.join(['f_%s' % x
                               for x in ispec])
            try:
                #
                # run UPSERT -- the DB provider must support it
                #
                (self
                 .execute('INSERT INTO %s (%s) VALUES (%s) '
                          'ON CONFLICT (%s) '
                          'DO UPDATE SET %s WHERE %s'
                          % (table, fnames, plchls, knames, setlst, idxlst),
                          (values + values + ivalues)))
                #
            except sqlite3.OperationalError:
                #
                # on SQLite3 < 3.24 fall back to INSERT OR REPLACE
                #
                self.execute('INSERT OR REPLACE INTO %s (%s) VALUES (%s)'
                             % (table, fnames, plchls), values)
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
