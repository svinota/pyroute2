import sqlite3
import threading
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

db = None
thread = None
schema = {ifinfmsg: dict(ifinfmsg.sql_schema())}


def createdb():
    global db
    global schema

    db = sqlite3.connect(':memory:')
    req_1 = 'CREATE TABLE interfaces ('
    req_2 = []
    for field in schema[ifinfmsg].items():
        req_2.append('f_%s %s' % field)
    req_2 = ','.join(req_2)
    req_3 = ')'
    req = '%s%s%s' % (req_1, req_2, req_3)
    db.execute(req)
    # interface specific
    db.execute('CREATE UNIQUE INDEX interfaces_idx ON interfaces'
               ' (f_index, f_IFLA_IFNAME)')
    return db


def load_netlink(event):
    global db
    global schema
    global thread

    #
    # simple barrier to work with the DB only from
    # one thread
    #
    if thread != threading.current_thread():
        return
    #
    # parse the event
    #
    fkeys = tuple(schema[ifinfmsg].keys())
    fields = ','.join(['f_%s' % x for x in fkeys])
    pch = ','.join('?' * len(fkeys))
    values = []
    for field in fkeys:
        values.append(event.get(field) or event.get_attr(field))

    req = 'INSERT OR REPLACE INTO interfaces (%s) VALUES (%s)' % (fields, pch)
    db.execute(req, values)


event_map = {ifinfmsg: load_netlink}
