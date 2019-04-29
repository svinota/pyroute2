'''
NDB
===

An experimental high-level RTNL management module.

.. warning::
    And it means really experimental.

Examples::

    from pyroute2 import NDB
    from pprint import pprint

    with NDB() as ndb:
        # ...
        for line ndb.routes.csv():
            print(line)
        # ...
        for record in ndb.interfaces.summary():
            print(record)
        # ...
        pprint(ndb.interfaces['eth0'])

        # ...
        pprint(ndb.interfaces[{'target': 'localhost',
                               'ifname': 'eth0'}])

        #
        # change object parameters
        #
        eth0 = ndb.interfaces['eth0']
        eth0['state'] = 'up'
        eth0.commit()

        #
        # create objects
        #
        test0 = ndb.interfaces.add(ifname='test0', kind='dummy')
        test0.commit()
        # ...
        test0.remove()
        test0.commit()

        #
        # it is mandatory to call ndb.close() or to use NDB
        # as a context manager
        #

Difference with IPDB
--------------------

NDB is designed to work with multiple event sources and with loads of
network objects.

Multiple sources::

    from pyroute2 import (NDB,
                          IPRoute,
                          NetNS,
                          RemoteIPRoute)

    sources = {'localhost': IPRoute(),
               'debian.test': RemoteIPRoute(protocol='ssh',
                                            hostname='192.168.122.54',
                                            username='netops'),
               'openbsd.test': RemoteIPRoute(protocol='ssh',
                                             hostname='192.168.122.60',
                                             username='netops'),
               'netns0': NetNS('netns0'),
               'docker': NetNS('/var/run/docker/netns/f2d2ba3e5987')}

    # NDB supports the context protocol, close() is called automatically
    with NDB(sources=sources) as ndb:
        # local interface
        print(ndb.interfaces[{'target': 'localhost',
                              'ifname': 'eth0'}])
        # remote interface
        print(ndb.interfaces[{'target': 'openbsd.test',
                              'ifname': 'ix0'}])
        # all the interfaces
        for i in ndb.interfaces.summary():
            print(i)

NDB stores all the data in an SQL database and creates objects on
demand. Statements like `ndb.interfaces['eth0']` create a new object
every time you run this statement. Thus::

    with NDB() as ndb:

        #
        # This will NOT work, as every line creates a new object
        #
        ndb.interfaces['eth0']['state'] = 'up'
        ndb.interfaces['eth0'].commit()

        #
        # This works
        #
        eth0 = ndb.interfaces['eth0']  # get the reference
        eth0['state'] = 'up'
        eth0.commit()

        #
        # The same with a context manager
        #
        with ndb.interfaces['eth0'] as eth0:
            eth0['state'] = 'up'
        # ---> <--- the context manager runs commit() at __exit__()


DB providers
------------

NDB supports different DB providers, now they are SQLite3 and PostgreSQL.
PostgreSQL access requires psycopg2 module::

    from pyroute2 import NDB

    # SQLite3 -- simple in-memory DB
    ndb = NDB(db_provider='sqlite3')

    # SQLite3 -- same as above
    ndb = NDB(db_provider='sqlite3',
              db_spec=':memory:')

    # SQLite3 -- file DB
    ndb = NDB(db_provider='sqlite3',
              db_spec='test.db')

    # PostgreSQL -- local DB
    ndb = NDB(db_provider='psycopg2',
              db_spec={'dbname': 'test'})

    # PostgreSQL -- remote DB
    ndb = NDB(db_provider='psycopg2',
              db_spec={'dbname': 'test',
                       'host': 'db1.example.com'})


'''
import gc
import json
import time
import atexit
import sqlite3
import logging
import weakref
import threading
import traceback
from functools import partial
from collections import OrderedDict
from pyroute2 import config
from pyroute2 import cli
from pyroute2.common import basestring
from pyroute2.ndb import dbschema
from pyroute2.ndb.events import (SyncStart,
                                 MarkFailed,
                                 DBMExitException,
                                 ShutdownException,
                                 InvalidateHandlerException)
from pyroute2.ndb.source import Source
from pyroute2.ndb.interface import Interface
from pyroute2.ndb.address import Address
from pyroute2.ndb.route import Route
from pyroute2.ndb.neighbour import Neighbour
from pyroute2.ndb.query import Query
from pyroute2.ndb.report import Report
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

try:
    import queue
except ImportError:
    import Queue as queue

try:
    import psycopg2
except ImportError:
    psycopg2 = None

log = logging.getLogger(__name__)


def target_adapter(value):
    #
    # MPLS target adapter for SQLite3
    #
    return json.dumps(value)


sqlite3.register_adapter(list, target_adapter)


class View(dict):
    '''
    The View() object returns RTNL objects on demand::

        ifobj1 = ndb.interfaces['eth0']
        ifobj2 = ndb.interfaces['eth0']
        # ifobj1 != ifobj2
    '''

    def __init__(self, ndb, table, match_src=None, match_pairs=None):
        self.ndb = ndb
        self.table = table
        self.event = table  # FIXME
        self.match_src = match_src
        self.match_pairs = match_pairs
        self.classes = OrderedDict()
        self.classes['interfaces'] = Interface
        self.classes['addresses'] = Address
        self.classes['neighbours'] = Neighbour
        self.classes['routes'] = Route

    def getmany(self, spec, table=None):
        return self.ndb.schema.get(table or self.table, spec)

    def getone(self, spec, table=None):
        for obj in self.getmany(spec, table):
            return obj

    def get(self, spec, table=None):
        return self.__getitem__(spec, table)

    @cli.change_pointer
    def add(self, **spec):
        spec['create'] = True
        return self[spec]

    def wait(self, **spec):
        ret = None

        # install a limited events queue -- for a possible immediate reaction
        evq = queue.Queue(maxsize=100)

        def handler(evq, target, event):
            # ignore the "queue full" exception
            #
            # if we miss some events here, nothing bad happens: we just
            # load them from the DB after a timeout, falling back to
            # the DB polling
            #
            # the most important here is not to allocate too much memory
            try:
                evq.put_nowait((target, event))
            except queue.Full:
                pass
        #
        hdl = partial(handler, evq)
        (self
         .ndb
         .register_handler(self
                           .ndb
                           .schema
                           .classes[self.event], hdl))
        #
        try:
            ret = self.__getitem__(spec)
            for key in spec:
                if ret[key] != spec[key]:
                    ret = None
                    break
        except KeyError:
            ret = None

        while ret is None:
            try:
                target, msg = evq.get(timeout=1)
            except queue.Empty:
                try:
                    ret = self.__getitem__(spec)
                    for key in spec:
                        if ret[key] != spec[key]:
                            ret = None
                            raise KeyError()
                    break
                except KeyError:
                    continue

            #
            for key, value in spec.items():
                if key == 'target' and value != target:
                    break
                elif value not in (msg.get(key),
                                   msg.get_attr(msg.name2nla(key))):
                    break
            else:
                while ret is None:
                    try:
                        ret = self.__getitem__(spec)
                    except KeyError:
                        time.sleep(0.1)

        #
        (self
         .ndb
         .unregister_handler(self
                             .ndb
                             .schema
                             .classes[self.event], hdl))

        del evq
        del hdl
        gc.collect()
        return ret

    def __getitem__(self, key, table=None):
        #
        # Construct a weakref handler for events.
        #
        # If the referent doesn't exist, raise the
        # exception to remove the handler from the
        # chain.
        #

        def wr_handler(wr, fname, *argv):
            try:
                return getattr(wr(), fname)(*argv)
            except:
                # check if the weakref became invalid
                if wr() is None:
                    raise InvalidateHandlerException()
                raise

        iclass = self.classes[table or self.table]
        ret = iclass(self,
                     key,
                     match_src=self.match_src,
                     match_pairs=self.match_pairs)
        wr = weakref.ref(ret)
        self.ndb._rtnl_objects.add(wr)
        for event, fname in ret.event_map.items():
            #
            # Do not trust the implicit scope and pass the
            # weakref explicitly via partial
            #
            (self
             .ndb
             .register_handler(event,
                               partial(wr_handler, wr, fname)))

        return ret

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()

    def keys(self):
        raise NotImplementedError()

    def items(self):
        raise NotImplementedError()

    @cli.show_result
    def count(self):
        return (self
                .ndb
                .schema
                .fetchone('SELECT count(*) FROM %s' % self.table))[0]

    def __len__(self):
        return self.count()

    def values(self):
        raise NotImplementedError()

    def _keys(self, iclass):
        return (['target', 'tflags'] +
                self.ndb.schema.compiled[iclass.view or iclass.table]['names'])

    def _dump(self, match=None):
        iclass = self.classes[self.table]
        keys = self._keys(iclass)

        spec, values = self._match(match, iclass, keys, iclass.table_alias)
        if iclass.dump and iclass.dump_header:
            yield iclass.dump_header
            for record in (self
                           .ndb
                           .schema
                           .fetch(iclass.dump + spec, values)):
                yield record
        else:
            yield tuple([iclass.nla2name(x) for x in keys])
            for record in (self
                           .ndb
                           .schema
                           .fetch('SELECT * FROM %s AS %s %s'
                                  % (iclass.view or iclass.table,
                                     iclass.table_alias,
                                     spec),
                                  values)):
                yield record

    def _csv(self, match=None, dump=None):
        if dump is None:
            dump = self._dump(match)
        for record in dump:
            row = []
            for field in record:
                if isinstance(field, int):
                    row.append('%i' % field)
                elif field is None:
                    row.append('')
                else:
                    row.append("'%s'" % field)
            row[-1] += '\n'
            yield ','.join(row)

    def _json(self, match=None, dump=None):
        if dump is None:
            dump = self._dump(match)
        fnames = next(dump)
        yield '['
        comma = ''
        for record in dump:
            lines = json.dumps(dict(zip(fnames, record)), indent=4).split('\n')
            yield '%s\n    %s' % (comma, lines[0])
            if not comma:
                comma = ','
            for line in lines[1:]:
                yield '\n    %s' % line
        yield '\n]\n'

    def _details(self, match=None, dump=None, format=None):
        # get the raw dump generator and get the fields description
        if dump is None:
            dump = self._dump(match)
        fnames = next(dump)
        if format == 'json':
            yield '['
            comma = ''
        # iterate all the records and yield a dict for every record
        for record in dump:
            obj = self[dict(zip(fnames, record))]
            if format == 'json':
                ret = OrderedDict()
                for key in sorted(obj):
                    ret[key] = obj[key]
                lines = json.dumps(ret, indent=4).split('\n')
                yield '%s\n    %s' % (comma, lines[0])
                if not comma:
                    comma = ','
                for line in lines[1:]:
                    yield '\n    %s' % line
            else:
                yield dict(obj)
        if format == 'json':
            yield '\n]\n'

    def _summary(self, match=None):
        iclass = self.classes[self.table]
        keys = self._keys(iclass)

        spec, values = self._match(match, iclass, keys, iclass.table_alias)
        if iclass.summary is not None:
            if iclass.summary_header is not None:
                yield iclass.summary_header
            for record in (self
                           .ndb
                           .schema
                           .fetch(iclass.summary + spec, values)):
                yield record
        else:
            header = tuple(['f_%s' % x for x in
                            ('target', ) +
                            self.ndb.schema.indices[iclass.table]])
            yield header
            key_fields = ','.join(header)
            for record in (self
                           .ndb
                           .schema
                           .fetch('SELECT %s FROM %s AS %s %s'
                                  % (key_fields,
                                     iclass.view or iclass.table,
                                     iclass.table_alias,
                                     spec), values)):
                yield record

    def _match(self, match, cls, keys, alias):
        values = []
        match = match or {}
        if self.match_src and self.match_pairs:
            for l_key, r_key in self.match_pairs.items():
                for src in self.match_src:
                    try:
                        match[l_key] = src[r_key]
                        break
                    except:
                        pass

        if match:
            spec = ' WHERE '
            conditions = []
            for key, value in match.items():
                keyc = []
                if cls.name2nla(key) in keys:
                    keyc.append(cls.name2nla(key))
                if key in keys:
                    keyc.append(key)
                if not keyc:
                    raise KeyError('key %s not found' % key)
                if len(keyc) == 1:
                    conditions.append('%s.f_%s = %s' % (alias, keyc[0],
                                                        self.ndb.schema.plch))
                    values.append(value)
                elif len(keyc) == 2:
                    conditions.append('(%s.f_%s = %s OR %s.f_%s = %s)'
                                      % (alias, keyc[0], self.ndb.schema.plch,
                                         alias, keyc[1], self.ndb.schema.plch))
                    values.append(value)
                    values.append(value)
            spec = ' WHERE %s' % ' AND '.join(conditions)
        else:
            spec = ''
        return spec, values

    @cli.show_result
    def dump(self, *argv, **kwarg):
        fmt = kwarg.pop('format',
                        kwarg.pop('fmt',
                                  self.ndb.config.get('show_format',
                                                      'native')))
        if fmt == 'native':
            return Report(self._dump(*argv, **kwarg))
        elif fmt == 'csv':
            return Report(self._csv(dump=self._dump(*argv, **kwarg)),
                          ellipsis=False)
        elif fmt == 'json':
            return Report(self._json(dump=self._dump(*argv, **kwarg)),
                          ellipsis=False)
        else:
            raise ValueError('format not supported')

    @cli.show_result
    def summary(self, *argv, **kwarg):
        fmt = kwarg.pop('format',
                        kwarg.pop('fmt',
                                  self.ndb.config.get('show_format',
                                                      'native')))
        if fmt == 'native':
            return Report(self._summary(*argv, **kwarg))
        elif fmt == 'csv':
            return Report(self._csv(dump=self._summary(*argv, **kwarg)),
                          ellipsis=False)
        elif fmt == 'json':
            return Report(self._json(dump=self._summary(*argv, **kwarg)),
                          ellipsis=False)
        else:
            raise ValueError('format not supported')

    @cli.show_result
    def details(self, *argv, **kwarg):
        fmt = kwarg.pop('format',
                        kwarg.pop('fmt',
                                  self.ndb.config.get('show_format',
                                                      'native')))
        if fmt == 'native':
            return Report(self._details(*argv, **kwarg))
        elif fmt == 'json':
            kwarg['format'] = 'json'
            return Report(self._details(*argv, **kwarg), ellipsis=False)
        else:
            raise ValueError('format not supported')


class SourcesView(View):

    def __init__(self, ndb):
        super(SourcesView, self).__init__(ndb, 'sources')
        self.classes['sources'] = Source
        self.cache = {}

    def add(self, **spec):
        spec = dict(spec)
        self.cache[spec['target']] = Source(self.ndb, **spec).start()
        return self.cache[spec['target']]

    def remove(self, target):
        return (self
                .cache
                .pop(target)
                .remove())

    def _keys(self, iclass):
        return ['target', 'kind']

    def wait(self, **spec):
        raise NotImplementedError()

    def _summary(self, *argv, **kwarg):
        return self._dump(*argv, **kwarg)

    def __getitem__(self, key, table=None):
        if isinstance(key, basestring):
            target = key
        elif isinstance(key, dict) and 'target' in key.keys():
            target = key['target']
        else:
            raise ValueError('key format not supported')

        return self.cache[target]


class NDB(object):

    def __init__(self,
                 sources=None,
                 db_provider='sqlite3',
                 db_spec=':memory:',
                 rtnl_log=False,
                 debug=False):

        self.ctime = self.gctime = time.time()
        self.schema = None
        self.config = {}
        self._debug = None
        self._db = None
        self._dbm_thread = None
        self._dbm_ready = threading.Event()
        self._dbm_shutdown = threading.Event()
        self._global_lock = threading.Lock()
        self._event_map = None
        self._event_queue = queue.Queue(maxsize=100)
        #
        if debug:
            self.debug(debug)
        #
        # fix sources prime
        if sources is None:
            sources = [{'target': 'localhost',
                        'kind': 'local',
                        'nlm_generator': 1}]
        elif not isinstance(sources, (list, tuple)):
            raise ValueError('sources format not supported')

        self.sources = SourcesView(self)
        self._nl = sources
        self._db_provider = db_provider
        self._db_spec = db_spec
        self._db_rtnl_log = rtnl_log
        atexit.register(self.close)
        self._rtnl_objects = set()
        self._dbm_ready.clear()
        self._dbm_thread = threading.Thread(target=self.__dbm__,
                                            name='NDB main loop')
        self._dbm_thread.setDaemon(True)
        self._dbm_thread.start()
        self._dbm_ready.wait()
        self.interfaces = View(self, 'interfaces')
        self.addresses = View(self, 'addresses')
        self.routes = View(self, 'routes')
        self.neighbours = View(self, 'neighbours')
        self.query = Query(self.schema)

    def _get_view(self, name, match_src=None, match_pairs=None):
        return View(self, name, match_src, match_pairs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @cli.show_result
    def show(self, *argv, **kwarg):
        ptr = self
        for word in argv:
            if hasattr(ptr, word):
                ptr = getattr(ptr, word)
            elif isinstance(ptr, dict):
                ptr = ptr[word]
            else:
                raise AttributeError('object not found')
        if hasattr(ptr, '__call__'):
            return ptr(**kwarg)
        elif hasattr(ptr, 'show'):
            return ptr.show(**kwarg)
        else:
            return ptr

    def debug(self, target=None):
        if target is None:
            return self._debug is not None

        if target == 'off':
            if self._debug is not None:
                self._debug['logger'].setLevel(logging.INFO)
                self._debug['logger'].removeHandler(self._debug['handler'])
                self._debug = None
            return

        if target == 'on':
            handler = logging.StreamHandler()
        elif isinstance(target, basestring):
            url = urlparse(target)
            if not url.scheme and url.path:
                handler = logging.FileHandler(url.path)
            elif url.scheme == 'syslog':
                handler = logging.SysLogHandler(address=url.netloc.split(':'))
            else:
                raise ValueError('logging scheme not supported')
        else:
            handler = target

        self._debug = {'logger': logging.getLogger(''), 'handler': handler}
        self._debug['logger'].addHandler(self._debug['handler'])
        self._debug['logger'].setLevel(logging.DEBUG)

    def register_handler(self, event, handler):
        if event not in self._event_map:
            self._event_map[event] = []
        self._event_map[event].append(handler)

    def unregister_handler(self, event, handler):
        self._event_map[event].remove(handler)

    def execute(self, *argv, **kwarg):
        return self.schema.execute(*argv, **kwarg)

    def close(self):
        with self._global_lock:
            if self._dbm_shutdown.is_set():
                return
            else:
                self._dbm_shutdown.set()

            if hasattr(atexit, 'unregister'):
                atexit.unregister(self.close)
            else:
                try:
                    atexit._exithandlers.remove((self.close, (), {}))
                except ValueError:
                    pass

            if self.schema:
                # release all the failed sources waiting for restart
                self._event_queue.put(('localhost', (ShutdownException(), )))
                # release all the sources
                for target, source in self.sources.cache.items():
                    source.close()
                # close the database
                self.schema.commit()
                self.schema.close()
                # shutdown the _dbm_thread
                self._event_queue.put(('localhost', (DBMExitException(), )))
                self._dbm_thread.join()

    def __initdb__(self):
        with self._global_lock:
            #
            # close the current db, if opened
            if self.schema:
                self.schema.commit()
                self.schema.close()
            if self._db_provider == 'sqlite3':
                self._db = sqlite3.connect(self._db_spec)
            elif self._db_provider == 'psycopg2':
                self._db = psycopg2.connect(**self._db_spec)

            if self.schema:
                self.schema.db = self._db

    def __dbm__(self):

        def default_handler(target, event):
            if isinstance(event, Exception):
                raise event
            logging.warning('unsupported event ignored: %s' % type(event))

        def check_sources_started(self, _locals, target, event):
            _locals['countdown'] -= 1
            if _locals['countdown'] == 0:
                self._dbm_ready.set()

        _locals = {'countdown': len(self._nl)}

        # init the events map
        event_map = {type(self._dbm_ready): [lambda t, x: x.set()],
                     MarkFailed: [lambda t, x: (self
                                                .schema
                                                .mark(t, 1))],
                     SyncStart: [partial(check_sources_started,
                                         self, _locals)]}
        self._event_map = event_map

        event_queue = self._event_queue

        self.__initdb__()
        self.schema = dbschema.init(self,
                                    self._db,
                                    self._db_provider,
                                    self._db_rtnl_log,
                                    id(threading.current_thread()))

        for spec in self._nl:
            self.sources.add(**spec)

        for (event, handlers) in self.schema.event_map.items():
            for handler in handlers:
                self.register_handler(event, handler)

        while True:
            target, events = event_queue.get()
            try:
                # if nlm_generator is True, an exception can come
                # here while iterating events
                for event in events:
                    handlers = event_map.get(event.__class__,
                                             [default_handler, ])
                    for handler in tuple(handlers):
                        try:
                            handler(target, event)
                        except InvalidateHandlerException:
                            try:
                                handlers.remove(handler)
                            except:
                                log.error('could not invalidate '
                                          'event handler:\n%s'
                                          % traceback.format_exc())
                        except ShutdownException:
                            for target, source in self.sources.cache.items():
                                source.shutdown.set()
                        except DBMExitException:
                            return
                        except:
                            log.error('could not load event:\n%s\n%s'
                                      % (event, traceback.format_exc()))
                    if time.time() - self.gctime > config.gc_timeout:
                        self.gctime = time.time()
                        for wr in tuple(self._rtnl_objects):
                            if wr() is None:
                                self._rtnl_objects.remove(wr)
            except:
                log.error('exception in source %s' % target)
                # restart the target
                self.sources[target].restart()
