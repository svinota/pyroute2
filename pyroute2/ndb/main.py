'''

NDB is a high level network management module. IT allows to manage interfaces,
routes, addresses etc. of connected systems, containers and network
namespaces.

NDB work with remote systems via ssh, in that case
`mitogen <https://github.com/dw/mitogen>`_ module is required. It is
possible to connect also OpenBSD and FreeBSD systems, but in read-only
mode for now.

Quick start
-----------

Print the routing infotmation in the CSV format::

    with NDB() as ndb:
        for record in ndb.routes.summary(format='csv'):
            print(record)

Print all the interface names on the system::

    with NDB() as ndb:
        print([x.ifname for x in ndb.interfaces.summary()])

Print IP addresses of interfaces in several network namespaces::

    nslist = ['netns01',
              'netns02',
              'netns03']

    with NDB() as ndb:
        for nsname in nslist:
            ndb.sources.add(netns=nsname)
        for record in ndb.interfaces.summary(format='json'):
            print(record)

Add an IP address on an interface::

    with NDB() as ndb:
        with ndb.interfaces['eth0'] as i:
            i.ipaddr.create(address='10.0.0.1', prefixlen=24).commit()
            # ---> <---  NDB waits until the address actually
            #            becomes available

Change an interface property::

    with NDB() as ndb:
        with ndb.interfaces['eth0'] as i:
            i['state'] = 'up'
            i['address'] = '00:11:22:33:44:55'
        # ---> <---  the commit() is called authomatically by
        #            the context manager's __exit__()


Key NDB features:
    * Asynchronously updated database of RTNL objects
    * Data integrity
    * Multiple data sources -- local, netns, remote
    * Fault tolerance and memory consumtion limits
    * Transactions

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
from pyroute2.ndb import schema
from pyroute2.ndb.events import (SyncStart,
                                 MarkFailed,
                                 DBMExitException,
                                 ShutdownException,
                                 InvalidateHandlerException)
from pyroute2.ndb.source import Source
from pyroute2.ndb.objects.interface import Interface
from pyroute2.ndb.objects.address import Address
from pyroute2.ndb.objects.route import Route
from pyroute2.ndb.objects.neighbour import Neighbour
from pyroute2.ndb.objects.rule import Rule
from pyroute2.ndb.objects.netns import NetNS
from pyroute2.ndb.query import Query
from pyroute2.ndb.report import (Report,
                                 Record)
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

    def __init__(self,
                 ndb,
                 table,
                 match_src=None,
                 match_pairs=None,
                 chain=None):
        self.ndb = ndb
        self.log = ndb.log.channel('view.%s' % table)
        self.table = table
        self.event = table  # FIXME
        self.chain = chain
        self.cache = {}
        self.constraints = {}
        self.match_src = match_src
        self.match_pairs = match_pairs
        self.classes = OrderedDict()
        self.classes['interfaces'] = Interface
        self.classes['addresses'] = Address
        self.classes['neighbours'] = Neighbour
        self.classes['routes'] = Route
        self.classes['rules'] = Rule
        self.classes['netns'] = NetNS

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def constraint(self, key, value):
        if value is None:
            self.constraints.pop(key)
        else:
            self.constraints[key] = value
        return self

    def getmany(self, spec, table=None):
        return self.ndb.schema.get(table or self.table, spec)

    def getone(self, spec, table=None):
        for obj in self.getmany(spec, table):
            return obj

    def get(self, spec, table=None):
        try:
            return self.__getitem__(spec, table)
        except KeyError:
            return None

    @cli.change_pointer
    def create(self, *argspec, **kwspec):
        spec = self.classes[self.table].adjust_spec(kwspec or argspec[0])
        if self.chain:
            spec['ndb_chain'] = self.chain
        spec['create'] = True
        return self[spec]

    @cli.change_pointer
    def add(self, *argspec, **kwspec):
        self.log.warning('''\n
        The name add() will be removed in future releases, use create()
        instead. If you believe that the idea to rename is wrong, please
        file your opinion to the project's bugtracker.

        The reason behind the rename is not to confuse interfaces.add() with
        bridge and bond port operations, that don't create any new interfaces
        but work on existing ones.
        ''')
        return self.create(*argspec, **kwspec)

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
        key = iclass.adjust_spec(key)
        if self.match_src:
            match_src = [x for x in self.match_src]
            match_pairs = dict(self.match_pairs)
        else:
            match_src = []
            match_pairs = {}
        if self.constraints:
            match_src.insert(0, self.constraints)
            for cskey, csvalue in self.constraints.items():
                match_pairs[cskey] = cskey
        ret = iclass(self,
                     key,
                     match_src=match_src,
                     match_pairs=match_pairs)

        # rtnl_object.key() returns a dcitionary that can not
        # be used as a cache key. Create here a tuple from it.
        # The key order guaranteed by the dictionary.
        cache_key = tuple(ret.key.items())

        # Iterate all the cache to remove unused and clean
        # (without any started transaction) objects.
        for ckey in tuple(self.cache):
            # Skip the current cache_key to avoid extra
            # cache del/add records in the logs
            if ckey == cache_key:
                continue
            # The number of referrers must be > 1, the first
            # one is the cache itself
            rcount = len(gc.get_referrers(self.cache[ckey]))
            # The number of changed rtnl_object fields must
            # be 0 which means that no transaction is started
            ccount = len(self.cache[ckey].changed)
            if rcount == 1 and ccount == 0:
                self.log.debug('cache del %s' % (ckey, ))
                del self.cache[ckey]

        # Cache only existing objects
        if ret.state == 'system':
            if cache_key in self.cache:
                self.log.debug('cache hit %s' % (cache_key, ))
                # Explicitly get rid of the created object
                del ret
                # The object from the cache has already
                # registered callbacks, simply return it
                ret = self.cache[cache_key]
                return ret
            else:
                self.log.debug('cache add %s' % (cache_key, ))
                # Otherwise create a cache entry
                self.cache[cache_key] = ret

        wr = weakref.ref(ret)
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

    def __iter__(self):
        return self.keys()

    def keys(self):
        for record in self.dump():
            yield record

    def values(self):
        for key in self.keys():
            yield self[key]

    def items(self):
        for key in self.keys():
            yield (key, self[key])

    @cli.show_result
    def count(self):
        return (self
                .ndb
                .schema
                .fetchone('SELECT count(*) FROM %s' % self.table))[0]

    def __len__(self):
        return self.count()

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
            yield ','.join(row)

    def _json(self, match=None, dump=None):
        if dump is None:
            dump = self._dump(match)
        fnames = next(dump)
        buf = []
        yield '['
        for record in dump:
            if buf:
                buf[-1] += ','
                for line in buf:
                    yield line
                buf = []
            lines = json.dumps(dict(zip(fnames, record)), indent=4).split('\n')
            buf.append('    {')
            for line in sorted(lines[1:-1]):
                buf.append('    %s,' % line.split(',')[0])
            buf[-1] = buf[-1][:-1]
            buf.append('    }')
        for line in buf:
            yield line
        yield ']'

    def _native(self, match=None, dump=None):
        if dump is None:
            dump = self._dump(match)
        fnames = next(dump)
        for record in dump:
            yield Record(fnames, record)

    def _details(self, match=None, dump=None, format=None):
        # get the raw dump generator and get the fields description
        if dump is None:
            dump = self._dump(match)
        fnames = next(dump)
        if format == 'json':
            yield '['
        buf = []
        # iterate all the records and yield a dict for every record
        for record in dump:
            obj = self[dict(zip(fnames, record))]
            if format == 'json':
                if buf:
                    buf[-1] += ','
                    for line in buf:
                        yield line
                    buf = []
                ret = OrderedDict()
                for key in sorted(obj):
                    ret[key] = obj[key]
                lines = json.dumps(ret, indent=4).split('\n')
                for line in lines:
                    buf.append('    %s' % line)
            else:
                yield dict(obj)
        if format == 'json':
            for line in buf:
                yield line
            yield ']'

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
            header = ('target', ) + self.ndb.schema.indices[iclass.table]
            yield tuple([iclass.nla2name(x) for x in header])
            key_fields = ','.join(['f_%s' % x for x in header])
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
            return Report(self._native(dump=self._dump(*argv, **kwarg)))
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
            return Report(self._native(dump=self._summary(*argv, **kwarg)))
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
        spec = dict(Source.defaults(spec))
        if 'event' not in spec:
            sync = True
            spec['event'] = threading.Event()
        else:
            sync = False
        self.cache[spec['target']] = Source(self.ndb, **spec).start()
        if sync:
            self.cache[spec['target']].event.wait()
        return self.cache[spec['target']]

    def remove(self, target):
        return (self
                .cache
                .pop(target)
                .remove())

    def keys(self):
        for key in self.cache:
            yield key

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


class Log(object):

    def __init__(self, log_id=None):
        self.logger = None
        self.state = False
        self.log_id = log_id or id(self)
        self.logger = logging.getLogger('pyroute2.ndb.%s' % self.log_id)
        self.main = self.channel('main')

    def __call__(self, target=None):
        if target is None:
            return self.logger is not None

        if self.logger is not None:
            for handler in tuple(self.logger.handlers):
                self.logger.removeHandler(handler)

        if target in ('off', False):
            if self.state:
                self.logger.setLevel(0)
                self.logger.addHandler(logging.NullHandler())
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

        fmt = '%(asctime)s %(levelname)8s %(name)s: %(message)s'
        formatter = logging.Formatter(fmt)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    @property
    def on(self):
        self.__call__(target='on')

    @property
    def off(self):
        self.__call__(target='off')

    def channel(self, name):
        return logging.getLogger('pyroute2.ndb.%s.%s' % (self.log_id, name))

    def debug(self, *argv, **kwarg):
        return self.main.debug(*argv, **kwarg)

    def info(self, *argv, **kwarg):
        return self.main.info(*argv, **kwarg)

    def warning(self, *argv, **kwarg):
        return self.main.warning(*argv, **kwarg)

    def error(self, *argv, **kwarg):
        return self.main.error(*argv, **kwarg)

    def critical(self, *argv, **kwarg):
        return self.main.critical(*argv, **kwarg)


class ReadOnly(object):

    def __init__(self, ndb):
        self.ndb = ndb

    def __enter__(self):
        self.ndb.schema.allow_write(False)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.ndb.schema.allow_write(True)


class NDB(object):

    def __init__(self,
                 sources=None,
                 db_provider='sqlite3',
                 db_spec=':memory:',
                 debug=False,
                 log=False):

        self.ctime = self.gctime = time.time()
        self.schema = None
        self.config = {}
        self.log = Log(log_id=id(self))
        self.readonly = ReadOnly(self)
        self._db = None
        self._dbm_thread = None
        self._dbm_ready = threading.Event()
        self._dbm_shutdown = threading.Event()
        self._global_lock = threading.Lock()
        self._event_map = None
        self._event_queue = queue.Queue(maxsize=100)
        #
        if log:
            self.log(log)
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
        self._db_rtnl_log = debug
        atexit.register(self.close)
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
        self.rules = View(self, 'rules')
        self.netns = View(self, 'netns')
        self.query = Query(self.schema)

    def _get_view(self, name, match_src=None, match_pairs=None, chain=None):
        return View(self, name, match_src, match_pairs, chain)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def register_handler(self, event, handler):
        if event not in self._event_map:
            self._event_map[event] = []
        self._event_map[event].append(handler)

    def unregister_handler(self, event, handler):
        self._event_map[event].remove(handler)

    def execute(self, *argv, **kwarg):
        return self.schema.execute(*argv, **kwarg)

    def close(self, flush=False):
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
                    source.close(flush)
                # flush the DB cache
                self.schema.commit()
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
            log.warning('unsupported event ignored: %s' % type(event))

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
        self.schema = schema.init(self,
                                  self._db,
                                  self._db_provider,
                                  self._db_rtnl_log,
                                  id(threading.current_thread()))

        for spec in self._nl:
            spec['event'] = None
            self.sources.add(**spec)

        for (event, handlers) in self.schema.event_map.items():
            for handler in handlers:
                self.register_handler(event, handler)

        try:
            while True:
                target, events = event_queue.get()
                try:
                    if events is None:
                        continue
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
                                for target, source in (self
                                                       .sources
                                                       .cache
                                                       .items()):
                                    source.shutdown.set()
                            except DBMExitException:
                                return
                            except:
                                log.error('could not load event:\n%s\n%s'
                                          % (event, traceback.format_exc()))
                        if time.time() - self.gctime > config.gc_timeout:
                            self.gctime = time.time()
                except Exception as e:
                    self.log.error('exception <%s> in source %s' % (e, target))
                    # restart the target
                    self.sources[target].restart(reason=e)
        finally:
            if self._db_rtnl_log:
                for table in self.schema.spec:
                    self.log.debug('rtnl log for <%s>' % table)
                    for record in (self
                                   .schema
                                   .fetch('SELECT * FROM %s_log' % table)):
                        self.log.debug('%s' % str(record))
            self.schema.connection.commit()
            self.schema.connection.close()
