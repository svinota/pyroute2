'''
Quick start
-----------

The goal of NDB is to provide an easy access to RTNL info and entities via
Python objects, like `pyroute2.ndb.objects.interface` (see also:
:ref:`ndbinterfaces`), `pyroute2.ndb.objects.route` (see also:
:ref:`ndbroutes`) etc. These objects do not
only reflect the system state for the time of their instantiation, but
continuously monitor the system for relevant updates. The monitoring is
done via netlink notifications, thus no polling. Also the objects allow
to apply changes back to the system and rollback the changes.

On the other hand it's too expensive to create Python objects for all the
available RTNL entities, e.g. when there are hundreds of interfaces and
thousands of routes. Thus NDB creates objects only upon request, when
the user calls `.create()` to create new objects or runs
`ndb.<view>[selector]` (e.g. `ndb.interfaces['eth0']`) to access an
existing object.

To list existing RTNL entities NDB uses objects of the class `RecordSet`
that `yield` individual `Record` objects for every entity (see also:
:ref:`ndbreports`). An object of the `Record` class is immutable, doesn't
monitor any updates, doesn't contain any links to other objects and essentially
behaves like a simple named tuple.

.. aafig::
    :scale: 80
    :textual:


      +---------------------+
      |                     |
      |                     |
      | `NDB() instance`    |
      |                     |
      |                     |
      +---------------------+
                 |
                 |
        +-------------------+
      +-------------------+ |
    +-------------------+ | |-----------+--------------------------+
    |                   | | |           |                          |
    |                   | | |           |                          |
    | `View()`          | | |           |                          |
    |                   | |-+           |                          |
    |                   |-+             |                          |
    +-------------------+               |                          |
                               +------------------+       +------------------+
                               |                  |       |                  |
                               |                  |       |                  |
                               | `.dump()`        |       | `.create()`      |
                               | `.summary()`     |       | `.__getitem__()` |
                               |                  |       |                  |
                               |                  |       |                  |
                               +------------------+       +------------------+
                                        |                           |
                                        |                           |
                                        v                           v
                              +-------------------+        +------------------+
                              |                   |      +------------------+ |
                              |                   |    +------------------+ | |
                              | `RecordSet()`     |    | `Interface()`    | | |
                              |                   |    | `Address()`      | | |
                              |                   |    | `Route()`        | | |
                              +-------------------+    | `Neighbour()`    | | |
                                        |              | `Rule()`         | |-+
                                        |              |  ...             |-+
                                        v              +------------------+
                                +-------------------+
                              +-------------------+ |
                            +-------------------+ | |
                            | `filter()`        | | |
                            | `select()`        | | |
                            | `transform()`     | | |
                            | `join()`          | |-+
                            |  ...              |-+
                            +-------------------+
                                        |
                                        v
                                +-------------------+
                              +-------------------+ |
                            +-------------------+ | |
                            |                   | | |
                            |                   | | |
                            | `Record()`        | | |
                            |                   | |-+
                            |                   |-+
                            +-------------------+

Here are some simple NDB usage examples. More info see in the reference
documentation below.

Print all the interface names on the system, assume we have an NDB
instance `ndb`::

    for interface in ndb.interfaces.dump():
        print(interface.ifname)

Print the routing information in the CSV format::

    for line in ndb.routes.summary().format('csv'):
        print(record)

.. note:: More on report filtering and formatting: :ref:`ndbreports`
.. note:: Since 0.5.11; versions 0.5.10 and earlier used
          syntax `summary(format='csv', match={...})`

Print IP addresses of interfaces in several network namespaces as::

    nslist = ['netns01',
              'netns02',
              'netns03']

    for nsname in nslist:
        ndb.sources.add(netns=nsname)

    for line in ndb.addresses.summary().format('json'):
        print(line)

Add an IP address on an interface::

    (ndb
     .interfaces['eth0']
     .add_ip('10.0.0.1/24')
     .commit())
    # ---> <---  NDB waits until the address actually

Change an interface property::

    (ndb
     .interfaces['eth0']
     .set('state', 'up')
     .set('address', '00:11:22:33:44:55')
     .commit()
    # ---> <---  NDB waits here for the changes to be applied

    # ... or with another syntax
    with ndb.interfaces['eth0'] as i:
        i['state'] = 'up'
        i['address'] = '00:11:22:33:44:55'
    # ---> <---  the commit() is called authomatically by
    #            the context manager's __exit__()

'''
import gc
import sys
import json
import time
import errno
import atexit
import sqlite3
import logging
import logging.handlers
import threading
import traceback
import ctypes
import ctypes.util
from functools import partial
from collections import OrderedDict
from pyroute2 import config
from pyroute2 import cli
from pyroute2.common import basestring
from pyroute2.ndb import schema
from pyroute2.ndb.events import (DBMExitException,
                                 ShutdownException,
                                 InvalidateHandlerException,
                                 RescheduleException)
from pyroute2.ndb.messages import (cmsg,
                                   cmsg_event,
                                   cmsg_failed,
                                   cmsg_sstart)
from pyroute2.ndb.source import Source
from pyroute2.ndb.auth_manager import check_auth
from pyroute2.ndb.auth_manager import AuthManager
from pyroute2.ndb.objects.interface import Interface
from pyroute2.ndb.objects.interface import Vlan
from pyroute2.ndb.objects.address import Address
from pyroute2.ndb.objects.route import Route
from pyroute2.ndb.objects.neighbour import Neighbour
from pyroute2.ndb.objects.rule import Rule
from pyroute2.ndb.objects.netns import NetNS
# from pyroute2.ndb.query import Query
from pyroute2.ndb.report import (RecordSet,
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


class PostgreSQLAdapter(object):

    def __init__(self, obj):
        self.obj = obj

    def getquoted(self):
        return "'%s'" % json.dumps(self.obj)


sqlite3.register_adapter(list, target_adapter)
sqlite3.register_adapter(dict, target_adapter)
if psycopg2 is not None:
    psycopg2.extensions.register_adapter(list, PostgreSQLAdapter)
    psycopg2.extensions.register_adapter(dict, PostgreSQLAdapter)


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
                 chain=None,
                 default_target='localhost',
                 auth_managers=None):
        self.ndb = ndb
        self.log = ndb.log.channel('view.%s' % table)
        self.table = table
        self.event = table  # FIXME
        self.chain = chain
        self.cache = {}
        if auth_managers is None:
            auth_managers = []
        if chain:
            auth_managers += chain.auth_managers
        self.default_target = default_target
        self.auth_managers = auth_managers
        self.constraints = {}
        self.classes = OrderedDict()
        self.classes['interfaces'] = Interface
        self.classes['addresses'] = Address
        self.classes['neighbours'] = Neighbour
        self.classes['routes'] = Route
        self.classes['rules'] = Rule
        self.classes['netns'] = NetNS
        self.classes['vlans'] = Vlan

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @property
    def context(self):
        if self.chain is not None:
            return self.chain.context
        else:
            return {}

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
        if self.chain:
            context = self.chain.context
        else:
            context = {}
        spec = (self
                .classes[self.table]
                .adjust_spec(kwspec or argspec[0], context))
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

    @check_auth('obj:read')
    def __getitem__(self, key, table=None):

        if self.chain:
            context = self.chain.context
        else:
            context = {}
        iclass = self.classes[table or self.table]
        if isinstance(key, Record):
            key = key._as_dict()
        key = iclass.adjust_spec(key, context)
        ret = iclass(self,
                     key,
                     load=False,
                     master=self.chain,
                     auth_managers=self.auth_managers)

        # rtnl_object.key() returns a dcitionary that can not
        # be used as a cache key. Create here a tuple from it.
        # The key order guaranteed by the dictionary.
        cache_key = tuple(ret.key.items())

        rtime = time.time()

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
            # Remove only expired items
            expired = (rtime - self.cache[ckey].atime) > config.cache_expire
            # The number of changed rtnl_object fields must
            # be 0 which means that no transaction is started
            if rcount == 1 and self.cache[ckey].clean and expired:
                self.log.debug('cache del %s' % (ckey, ))
                self.cache.pop(ckey, None)

        if cache_key in self.cache:
            self.log.debug('cache hit %s' % (cache_key, ))
            # Explicitly get rid of the created object
            del ret
            # The object from the cache has already
            # registered callbacks, simply return it
            ret = self.cache[cache_key]
            ret.atime = rtime
            return ret
        else:
            # Cache only existing objects
            if ret.load_sql():
                self.log.debug('cache add %s' % (cache_key, ))
                self.cache[cache_key] = ret

        ret.register()
        return ret

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()

    def __iter__(self):
        return self.keys()

    @check_auth('obj:list')
    def keys(self):
        for record in self.dump():
            yield record

    @check_auth('obj:list')
    def values(self):
        for key in self.keys():
            yield self[key]

    @check_auth('obj:list')
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

    def _native(self, dump):
        fnames = next(dump)
        for record in dump:
            yield Record(fnames, record)

    @cli.show_result
    @check_auth('obj:list')
    def dump(self):
        iclass = self.classes[self.table]
        return RecordSet(self._native(iclass.dump(self)))

    @cli.show_result
    @check_auth('obj:list')
    def summary(self):
        iclass = self.classes[self.table]
        return RecordSet(self._native(iclass.summary(self)))


class SourcesView(View):

    def __init__(self, ndb):
        super(SourcesView, self).__init__(ndb, 'sources')
        self.classes['sources'] = Source
        self.cache = {}
        self.lock = threading.Lock()

    def async_add(self, **spec):
        spec = dict(Source.defaults(spec))
        self.cache[spec['target']] = Source(self.ndb, **spec).start()
        return self.cache[spec['target']]

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

    def remove(self, target, code=errno.ECONNRESET, sync=True):
        with self.lock:
            if target in self.cache:
                source = self.cache[target]
                source.close(code=code, sync=sync)
                return self.cache.pop(target)

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

    def __call__(self, target=None, level=logging.INFO):
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

        if target in ('on', 'stderr'):
            handler = logging.StreamHandler()
        elif target == 'debug':
            handler = logging.StreamHandler()
            level = logging.DEBUG
        elif isinstance(target, basestring):
            url = urlparse(target)
            if not url.scheme and url.path:
                handler = logging.FileHandler(url.path)
            elif url.scheme == 'syslog':
                handler = (logging
                           .handlers
                           .SysLogHandler(address=url.netloc.split(':')))
            else:
                raise ValueError('logging scheme not supported')
        else:
            handler = target

        # set formatting only for new created logging handlers
        if handler is not target:
            fmt = '%(asctime)s %(levelname)8s %(name)s: %(message)s'
            formatter = logging.Formatter(fmt)
            handler.setFormatter(formatter)

        self.logger.addHandler(handler)
        self.logger.setLevel(level)

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


class DeadEnd(object):

    def put(self, *argv, **kwarg):
        raise ShutdownException('shutdown in progress')


class EventQueue(object):

    def __init__(self, *argv, **kwarg):
        self._bypass = self._queue = queue.Queue(*argv, **kwarg)

    def put(self, *argv, **kwarg):
        return self._queue.put(*argv, **kwarg)

    def shutdown(self):
        self._queue = DeadEnd()

    def bypass(self, *argv, **kwarg):
        return self._bypass.put(*argv, **kwarg)

    def get(self, *argv, **kwarg):
        return self._bypass.get(*argv, **kwarg)

    def qsize(self):
        return self._bypass.qsize()


def Events(*argv):
    for sequence in argv:
        if sequence is not None:
            for item in sequence:
                yield item


class AuthProxy(object):

    def __init__(self, ndb, auth_managers):
        self._ndb = ndb
        self._auth_managers = auth_managers

        for spec in (('interfaces', 'localhost'),
                     ('addresses', 'localhost'),
                     ('routes', 'localhost'),
                     ('neighbours', 'localhost'),
                     ('rules', 'localhost'),
                     ('netns', 'nsmanager'),
                     ('vlans', 'localhost')):
            view = View(self._ndb,
                        spec[0],
                        default_target=spec[1],
                        auth_managers=self._auth_managers)
            setattr(self, spec[0], view)


class NDB(object):

    def __init__(self,
                 sources=None,
                 db_provider='sqlite3',
                 db_spec=':memory:',
                 rtnl_debug=False,
                 log=False,
                 auto_netns=False,
                 libc=None):

        self.ctime = self.gctime = time.time()
        self.schema = None
        self.config = {}
        self.libc = libc or ctypes.CDLL(ctypes.util.find_library('c'),
                                        use_errno=True)
        self.log = Log(log_id=id(self))
        self.readonly = ReadOnly(self)
        self._auto_netns = auto_netns
        self._db = None
        self._dbm_thread = None
        self._dbm_ready = threading.Event()
        self._dbm_shutdown = threading.Event()
        self._global_lock = threading.Lock()
        self._event_map = None
        self._event_queue = EventQueue(maxsize=100)
        #
        if log:
            if isinstance(log, basestring):
                self.log(log)
            elif isinstance(log, (tuple, list)):
                self.log(*log)
            elif isinstance(log, dict):
                self.log(**log)
            else:
                raise TypeError('wrong log spec format')
        #
        # fix sources prime
        if sources is None:
            sources = [{'target': 'localhost',
                        'kind': 'local',
                        'nlm_generator': 1}]
            if sys.platform.startswith('linux'):
                sources.append({'target': 'nsmanager',
                                'kind': 'nsmanager'})
        elif not isinstance(sources, (list, tuple)):
            raise ValueError('sources format not supported')

        self.sources = SourcesView(self)
        self._nl = sources
        self._db_provider = db_provider
        self._db_spec = db_spec
        self._db_rtnl_log = rtnl_debug
        atexit.register(self.close)
        self._dbm_ready.clear()
        self._dbm_autoload = set()
        self._dbm_thread = threading.Thread(target=self.__dbm__,
                                            name='NDB main loop')
        self._dbm_thread.setDaemon(True)
        self._dbm_thread.start()
        self._dbm_ready.wait()
        for event in tuple(self._dbm_autoload):
            event.wait()
        self._dbm_autoload = None
        am = AuthManager({'obj:list': True,
                          'obj:read': True,
                          'obj:modify': True},
                         self.log.channel('auth'))
        for spec in (('interfaces', 'localhost'),
                     ('addresses', 'localhost'),
                     ('routes', 'localhost'),
                     ('neighbours', 'localhost'),
                     ('rules', 'localhost'),
                     ('netns', 'nsmanager'),
                     ('vlans', 'localhost')):
            view = View(self,
                        spec[0],
                        default_target=spec[1],
                        auth_managers=[am])
            setattr(self, spec[0], view)
        # self.query = Query(self.schema)

    def _get_view(self, name, chain=None):
        return View(self, name, chain)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def auth_proxy(self, auth_manager):
        return AuthProxy(self, [auth_manager, ])

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
            # shutdown the _dbm_thread
            self._event_queue.shutdown()
            self._event_queue.bypass((cmsg(None, ShutdownException()), ))
            self._dbm_thread.join()

    def __dbm__(self):

        def default_handler(target, event):
            if isinstance(getattr(event, 'payload', None), Exception):
                raise event.payload
            log.warning('unsupported event ignored: %s' % type(event))

        def check_sources_started(self, _locals, target, event):
            _locals['countdown'] -= 1
            if _locals['countdown'] == 0:
                self._dbm_ready.set()

        _locals = {'countdown': len(self._nl)}

        # init the events map
        event_map = {cmsg_event: [lambda t, x: x.payload.set()],
                     cmsg_failed: [lambda t, x: (self
                                                 .schema
                                                 .mark(t, 1))],
                     cmsg_sstart: [partial(check_sources_started,
                                           self, _locals)]}
        self._event_map = event_map

        event_queue = self._event_queue

        if self._db_provider == 'sqlite3':
            self._db = sqlite3.connect(self._db_spec)
        elif self._db_provider == 'psycopg2':
            self._db = psycopg2.connect(**self._db_spec)

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

        stop = False
        reschedule = []
        while not stop:
            events = Events(event_queue.get(), reschedule)
            reschedule = []
            try:
                for event in events:
                    handlers = event_map.get(event.__class__,
                                             [default_handler, ])
                    for handler in tuple(handlers):
                        try:
                            target = event['header']['target']
                            handler(target, event)
                        except RescheduleException:
                            if 'rcounter' not in event['header']:
                                event['header']['rcounter'] = 0
                            if event['header']['rcounter'] < 3:
                                event['header']['rcounter'] += 1
                                self.log.debug('reschedule %s' % (event, ))
                                reschedule.append(event)
                            else:
                                self.log.error('drop %s' % (event, ))
                        except InvalidateHandlerException:
                            try:
                                handlers.remove(handler)
                            except:
                                self.log.error('could not invalidate '
                                               'event handler:\n%s'
                                               % traceback.format_exc())
                        except ShutdownException:
                            stop = True
                            break
                        except DBMExitException:
                            return
                        except:
                            self.log.error('could not load event:\n%s\n%s'
                                           % (event, traceback.format_exc()))
                    if time.time() - self.gctime > config.gc_timeout:
                        self.gctime = time.time()
            except Exception as e:
                self.log.error('exception <%s> in source %s' % (e, target))
                # restart the target
                try:
                    self.sources[target].restart(reason=e)
                except KeyError:
                    pass

        # release all the sources
        for target in tuple(self.sources.cache):
            source = self.sources.remove(target, sync=False)
            if source is not None and source.th is not None:
                source.shutdown.set()
                source.th.join()
                self.log.debug('flush DB for the target %s' % target)
                self.schema.flush(target)

        # close the database
        self.schema.commit()
        self.schema.close()
