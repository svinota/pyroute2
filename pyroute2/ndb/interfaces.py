import sqlite3
import threading
from functools import partial
from collections import OrderedDict
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg


class Interfaces(object):

    db = None
    thread = None
    event_map = None
    schema = {'interfaces': OrderedDict(ifinfmsg.sql_schema()),
              'neighbours': OrderedDict(ndmsg.sql_schema())}
    classes = {'interfaces': ifinfmsg,
               'neighbours': ndmsg}

    def __init__(self, db_uri, tid):
        self.thread = tid
        #
        # ACHTUNG!
        # check_same_thread=False
        #
        # Do NOT write into the DB from ANY of the methods except
        # those which are called from the __dbm__ thread!
        #
        self.db = sqlite3.connect(db_uri, check_same_thread=False)
        self.create_table('interfaces')
        self.create_table('neighbours')
        self.db.execute('CREATE UNIQUE INDEX interfaces_idx ON interfaces'
                        ' (f_index, f_IFLA_IFNAME)')
        self.db.execute('CREATE UNIQUE INDEX neighbours_idx ON neighbours'
                        ' (f_ifindex, f_NDA_LLADDR)')

    def create_table(self, table):
        req = []
        for field in self.schema[table].items():
            #
            # Why f_?
            # 'Cause there are attributes like 'index' and such
            # names may not be used in SQL statements
            #
            req.append('f_%s %s' % field)
        req = ','.join(req)
        req = 'CREATE TABLE %s (%s)' % (table, req)
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

    def load_netlink(self, table, event):
        #
        # Simple barrier to work with the DB only from
        # one thread
        #
        # ? make a decorator ?
        if self.thread != id(threading.current_thread()):
            return
        #
        # Parse the event
        #
        fkeys = tuple(self.schema[table].keys())
        fields = ','.join(['f_%s' % x for x in fkeys])
        pch = ','.join('?' * len(fkeys))
        values = []
        for field in fkeys:
            values.append(event.get(field) or event.get_attr(field))

        req = 'INSERT OR REPLACE INTO %s (%s) VALUES (%s)' % (table,
                                                              fields,
                                                              pch)
        self.db.execute(req, values)


def init(db_uri, tid):
    ret = Interfaces(db_uri, tid)
    ret.event_map = {ifinfmsg: partial(ret.load_netlink, 'interfaces'),
                     ndmsg: partial(ret.load_netlink, 'neighbours')}
    return ret
