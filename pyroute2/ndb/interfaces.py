import sqlite3
import threading
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


class Interfaces(object):

    db = None
    thread = None
    event_map = None
    schema = {ifinfmsg: dict(ifinfmsg.sql_schema())}

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
        req = []
        for field in self.schema[ifinfmsg].items():
            #
            # Why f_?
            # 'Cause there are attributes like 'index' and such
            # names may not be used in SQL statements
            #
            req.append('f_%s %s' % field)
        req = ','.join(req)
        req = 'CREATE TABLE interfaces (%s)' % (req)
        self.db.execute(req)
        self.db.execute('CREATE UNIQUE INDEX interfaces_idx ON interfaces'
                        ' (f_index, f_IFLA_IFNAME)')

    def get(self, spec):
        #
        # Retrieve info from the DB
        #
        # ndb.interfaces.get({'ifname': 'eth0'})
        #
        conditions = []
        values = []
        for key, value in spec.items():
            if key not in [x[0] for x in ifinfmsg.fields]:
                key = ifinfmsg.name2nla(key)
            conditions.append('f_%s = ?' % key)
            values.append(value)
        req = 'SELECT * FROM interfaces WHERE %s' % ' AND '.join(conditions)
        return tuple(self.db.execute(req, values).fetchall())

    def load_netlink(self, event):
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
        fkeys = tuple(self.schema[ifinfmsg].keys())
        fields = ','.join(['f_%s' % x for x in fkeys])
        pch = ','.join('?' * len(fkeys))
        values = []
        for field in fkeys:
            values.append(event.get(field) or event.get_attr(field))

        req = 'INSERT OR REPLACE INTO interfaces (%s) VALUES (%s)' % (fields,
                                                                      pch)
        self.db.execute(req, values)


def init(db_uri, tid):
    ret = Interfaces(db_uri, tid)
    ret.event_map = {ifinfmsg: ret.load_netlink}
    return ret
