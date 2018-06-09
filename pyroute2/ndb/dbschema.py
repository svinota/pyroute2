import uuid
import threading
from functools import partial
from collections import OrderedDict
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
    classes = {'interfaces': ifinfmsg,
               'addresses': ifaddrmsg,
               'neighbours': ndmsg,
               'routes': rtmsg}
    index = {'interfaces': ('index',
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

    foreign_key = {'addresses': [('(f_index)', 'interfaces(f_index)'), ],
                   'neighbours': [('(f_ifindex)', 'interfaces(f_index)'), ],
                   'routes': [('(f_RTA_OIF)', 'interfaces(f_index)'),
                              ('(f_RTA_IIF)', 'interfaces(f_index)')],
                   'nh': [('(f_route_id)', 'routes(f_route_id)'), ]}

    def __init__(self, db, tid):
        self.thread = tid
        self.db = db
        self.db.execute('PRAGMA foreign_keys = ON')
        for table in ('interfaces',
                      'addresses',
                      'neighbours',
                      'routes',
                      'nh'):
            self.create_table(table)

    def create_table(self, table):
        req = ['target']
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
        if table in self.foreign_key:
            for key in self.foreign_key[table]:
                req.append('FOREIGN KEY %s REFERENCES %s '
                           'ON UPDATE CASCADE '
                           'ON DELETE CASCADE ' % key)
        req = ','.join(req)
        req = ('CREATE TABLE IF NOT EXISTS '
               '%s (%s)' % (table, req))
        self.db.execute(req)
        index = ','.join(['target'] + ['f_%s' % x for x in self.index[table]])
        req = ('CREATE UNIQUE INDEX IF NOT EXISTS '
               '%s_idx ON %s (%s)' % (table, table, index))
        self.db.execute(req)

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
            keys = ['target = ?']
            values = [target]
            for key in self.index['routes']:
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
        # The event type
        #
        if event['header'].get('type', 0) % 2:
            #
            # Delete an object
            #
            conditions = ['target = ?']
            values = [target]
            for key in self.index[table]:
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
            fields = ','.join(['target'] + ['f_%s' % x for x in fkeys])
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
