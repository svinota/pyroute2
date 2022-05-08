import uuid
import sqlite3


def test_file_backup(context):
    filename = str(uuid.uuid4()) + '-backup.db'
    context.ndb.backup(filename)
    backup = sqlite3.connect(filename)
    cursor = backup.cursor()
    cursor.execute('SELECT f_IFLA_IFNAME FROM interfaces WHERE f_index > 0')
    interfaces_from_backup = {x[0] for x in cursor.fetchall()}
    interfaces_from_ndb = {
        x.ifname for x in context.ndb.interfaces.summary().select('ifname')
    }
    assert interfaces_from_ndb == interfaces_from_backup
