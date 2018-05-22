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
        self.db = sqlite3.connect(db_uri)
        req = []
        for field in self.schema[ifinfmsg].items():
            req.append('f_%s %s' % field)
        req = ','.join(req)
        req = 'CREATE TABLE interfaces (%s)' % (req)
        self.db.execute(req)
        self.db.execute('CREATE UNIQUE INDEX interfaces_idx ON interfaces'
                        ' (f_index, f_IFLA_IFNAME)')

    def load_netlink(self, event):
        #
        # simple barrier to work with the DB only from
        # one thread
        #
        if self.thread != id(threading.current_thread()):
            return
        #
        # parse the event
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
