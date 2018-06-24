import sqlite3
try:
    import psycopg2
except ImportError:
    psycopg2 = None

sql_err = {'sqlite3': {'ProgrammingError': sqlite3.OperationalError,
                       'IntegrityError': sqlite3.IntegrityError}}
if psycopg2 is not None:
    sql_err['psycopg2'] = {'ProgrammingError': psycopg2.ProgrammingError,
                           'IntegrityError': psycopg2.IntegrityError}
