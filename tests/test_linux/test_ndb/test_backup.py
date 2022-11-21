import sqlite3
import sys
import uuid

import pytest


@pytest.mark.skipif(
    sys.version_info < (3, 7),
    reason='SQLite3 backup not supported on this Python version',
)
def test_file_backup(context):
    filename = str(uuid.uuid4()) + '-backup.db'
    context.ndb.backup(filename)
    backup = sqlite3.connect(filename)
    cursor = backup.cursor()
    cursor.execute('SELECT f_IFLA_IFNAME FROM interfaces WHERE f_index > 0')
    interfaces_from_backup = {x[0] for x in cursor.fetchall()}
    with context.ndb.interfaces.summary() as summary:
        interfaces_from_ndb = {x.ifname for x in summary}
    assert interfaces_from_ndb == interfaces_from_backup
