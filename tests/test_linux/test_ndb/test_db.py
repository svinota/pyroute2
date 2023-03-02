import sqlite3

import pytest

from pyroute2 import NDB

try:
    import psycopg2
except ImportError:
    pytest.skip('no psycopg2 module installed', allow_module_level=True)


def test_no_cleanup(spec):
    # start and stop the DB, leaving all the data in the DB file
    NDB(
        db_provider='sqlite3',
        db_spec=spec.db_spec,
        db_cleanup=False,
        log=spec.log_spec,
    ).close()

    # open the DB file
    db = sqlite3.connect(spec.db_spec)
    cursor = db.cursor()
    cursor.execute('SELECT * FROM interfaces')
    interfaces = cursor.fetchall()

    # at least two records: idx 0 and loopback
    assert len(interfaces) > 1
    # all the interfaces must be of the same source, 'localhost'
    assert set([x[0] for x in interfaces]) == set(('localhost',))


def test_postgres_fail(spec):
    try:
        NDB(
            db_provider='postgres',
            db_spec={'dbname': 'some-nonsense-db-name'},
            log=spec.log_spec,
        ).close()
    except psycopg2.OperationalError:
        return

    raise Exception('postgresql exception was expected')
