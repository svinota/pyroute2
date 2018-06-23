import time
import uuid
import sqlite3
import threading
from functools import partial
from collections import OrderedDict
from pyroute2 import config
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh


class DBSchema(object):

    db = None
    thread = None
    event_map = None

    schema = {'interfaces': OrderedDict(ifinfmsg.sql_schema()),
              'addresses': OrderedDict(ifaddrmsg.sql_schema()),
              'neighbours': OrderedDict(ndmsg.sql_schema()),
              'routes': OrderedDict(rtmsg.sql_schema()),
              'nh': OrderedDict(nh.sql_schema())}
    key_defaults = {}

    snapshots = {}  # <table_name>: <obj_weakref>

    classes = {'interfaces': ifinfmsg,
               'addresses': ifaddrmsg,
               'neighbours': ndmsg,
               'routes': rtmsg}

    indices = {'interfaces': ('index',
                              'IFLA_IFNAME'),
               'addresses': ('index',
                             'IFA_ADDRESS',
                             'IFA_LOCAL'),
               'neighbours': ('ifindex',
                              'NDA_LLADDR'),
               'routes': ('family',
                          'tos',
                          'dst_len',
                          'RTA_TABLE',
                          'RTA_DST',
                          'RTA_PRIORITY'),
               'nh': ('route_id',
                      'nh_id')}

    foreign_keys = {'addresses': [{'cols': ('f_target', 'f_index'),
                                   'pcls': ('f_target', 'f_index'),
                                   'parent': 'interfaces'}],
                    'neighbours': [{'cols': ('f_target', 'f_ifindex'),
                                    'pcls': ('f_target', 'f_index'),
                                    'parent': 'interfaces'}],
                    'routes': [{'cols': ('f_target', 'f_RTA_OIF'),
                                'pcls': ('f_target', 'f_index'),
                                'parent': 'interfaces'},
                               {'cols': ('f_target', 'f_RTA_IIF'),
                                'pcls': ('f_target', 'f_index'),
                                'parent': 'interfaces'}],
                    'nh': [{'cols': ('f_route_id', ),
                            'pcls': ('f_route_id', ),
                            'parent': 'routes'}]}

    def __init__(self, db, tid):
        self.thread = tid
        self.db = db
        self.db.execute('PRAGMA foreign_keys = ON')
        self.gctime = self.ctime = time.time()
        for table in ('interfaces',
                      'addresses',
                      'neighbours',
                      'routes',
                      'nh'):
            self.create_table(table)

    def execute(self, *argv, **kwarg):
        return self.db.execute(*argv, **kwarg)

    def close(self):
        return self.db.close()

    def commit(self):
        return self.db.commit()

    def create_table(self, table):
        req = ['f_target TEXT NOT NULL']
        self.key_defaults[table] = {}
        for field in self.schema[table].items():
            #
            # Why f_?
            # 'Cause there are attributes like 'index' and such
            # names may not be used in SQL statements
            #
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
                    self.db.execute('CREATE UNIQUE INDEX '
                                    'IF NOT EXISTS %s ON %s' %
                                    (idxname, spec[1]))

        req = ','.join(req)
        req = ('CREATE TABLE IF NOT EXISTS '
               '%s (%s)' % (table, req))
        self.db.execute(req)
        index = ','.join(['f_target'] + ['f_%s' % x for x
                                         in self.indices[table]])
        req = ('CREATE UNIQUE INDEX IF NOT EXISTS '
               '%s_idx ON %s (%s)' % (table, table, index))
        self.db.execute(req)

    def save_deps(self, parent, objid, wref):
        #
        # Stage 1 of saving deps.
        #
        # Create tables for direct dependencies and copy there the data
        # matching the object.
        #
        # E.g.::
        #
        #   interfaces -> addresses
        #                 routes
        #                 neighbours
        #
        obj = wref()
        for table, keys in self.foreign_keys.items():
            new_table = '%s_%s' % (table, objid)
            #
            # There may be multiple foreign keys
            for key in keys:
                #
                # Work on matching tables
                if key['parent'] == parent:
                    #
                    # Create the WHERE clause
                    reqs = []
                    for cols in key['cols']:
                        reqs.append('%s = ?' % cols)
                    values = [obj[self
                                  .classes[parent]
                                  .nla2name(x[2:])] for x in key['pcls']]
                    #
                    # Create the tables as a copy of the related data...
                    #
                    try:
                        self.db.execute('CREATE TABLE %s AS '
                                        'SELECT * FROM %s WHERE %s' %
                                        (new_table, table,
                                         ' AND '.join(reqs)),
                                        values)
                    #
                    # ... or append the data, if the table is created --
                    # happens when there are multiple foreign keys, as
                    # for routes
                    #
                    except sqlite3.OperationalError:
                        self.db.execute('INSERT OR REPLACE INTO %s '
                                        'SELECT * FROM %s WHERE %s' %
                                        (new_table, table,
                                         ' AND '.join(reqs)),
                                        values)
                    #
                    # Save the reference into the registry.
                    #
                    # The registry should be cleaned up periodically.
                    # When the wref() call returns None, the record
                    # should be removed from the registry and the table
                    # should be dropped.
                    #
                    self.snapshots[new_table] = wref
                    self.save_deps_s2(table, new_table, objid, wref)

    def save_deps_s2(self, parent, snp_table, objid, wref):
        # Stage 2 of saving deps.
        #
        # Create additional tables to track nested deps (recursively)
        #
        # E.g.::
        #
        #   routes -> nh
        #
        for table, keys in self.foreign_keys.items():
            new_table = '%s_%s' % (table, objid)
            #
            # There may be multiple foreign keys
            for key in keys:
                #
                # Work on matching tables
                if key['parent'] == parent:
                    try:
                        self.db.execute('CREATE TABLE %s AS '
                                        'SELECT * FROM %s WHERE '
                                        '(%s) IN (SELECT %s FROM %s)' %
                                        (new_table, table,
                                         ','.join(key['cols']),
                                         ','.join(key['pcls']),
                                         snp_table))
                    except sqlite3.OperationalError:
                        self.db.execute('INSERT OR REPLACE INTO %s '
                                        'SELECT * FROM %s WHERE '
                                        '(%s) IN (SELECT %s FROM %s)' %
                                        (new_table, table,
                                         ','.join(key['cols']),
                                         ','.join(key['pcls']),
                                         snp_table))
                    self.snapshots[new_table] = wref
                    self.save_deps_s2(table, new_table, objid, wref)

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
            conditions.append('f_%s = ?' % key)
            values.append(value)
        req = 'SELECT * FROM %s WHERE %s' % (table, ' AND '.join(conditions))
        for record in self.db.execute(req, values).fetchall():
            ret.append(dict(zip(self.schema[table].keys(), record)))
        return ret

    def load_rtmsg(self, target, event):
        mp = event.get_attr('RTA_MULTIPATH')

        if (not event['header']['type'] % 2) and mp:
            # create & mp route
            #
            # create key
            keys = ['f_target = ?']
            values = [target]
            for key in self.indices['routes']:
                keys.append('f_%s = ?' % key)
                values.append(event.get(key) or event.get_attr(key))
            #
            spec = 'WHERE %s' % ' AND '.join(keys)
            s_req = 'SELECT f_route_id FROM routes %s' % spec
            #
            # get existing route_id
            route_id = self.db.execute(s_req, values).fetchall()
            if route_id:
                #
                # if exists
                route_id = route_id[0][0]
                #
                # flush all previous MP hops
                d_req = 'DELETE FROM nh WHERE f_route_id= ?'
                self.db.execute(d_req, (route_id, ))
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
                self.load_netlink('nh', target, mp[idx])
            #
            # we're done with an MP-route, just exit
            return
        #
        # ... or work on a regular route
        self.load_netlink("routes", target, event)

    def load_netlink(self, table, target, event):
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
                    self.db.execute('DROP TABLE %s' % name)
        #
        # The event type
        #
        if event['header'].get('type', 0) % 2:
            #
            # Delete an object
            #
            conditions = ['f_target = ?']
            values = [target]
            for key in self.indices[table]:
                conditions.append('f_%s = ?' % key)
                value = event.get(key) or event.get_attr(key)
                if value is None:
                    value = self.key_defaults[table][key]
                values.append(value)
            self.db.execute('DELETE FROM %s WHERE'
                            ' %s' % (table, ' AND '.join(conditions)), values)
        else:
            #
            # Create or set an object
            #
            fkeys = tuple(self.schema[table].keys())
            fields = ','.join(['f_target'] + ['f_%s' % x for x in fkeys])
            pch = ','.join('?' * (len(fkeys) + 1))
            values = [target]
            for field in fkeys:
                value = event.get_attr(field) or event.get(field)
                values.append(value)
            try:
                self.db.execute('INSERT OR REPLACE INTO %s (%s)'
                                ' VALUES (%s)' % (table, fields, pch), values)
            except Exception:
                #
                # A good question, what should we do here
                import traceback
                traceback.print_exc()


def init(db, tid):
    ret = DBSchema(db, tid)
    ret.event_map = {ifinfmsg: partial(ret.load_netlink, 'interfaces'),
                     ifaddrmsg: partial(ret.load_netlink, 'addresses'),
                     ndmsg: partial(ret.load_netlink, 'neighbours'),
                     rtmsg: ret.load_rtmsg}
    return ret
