'''
NDB is a high level network management module. IT allows to manage interfaces,
routes, addresses etc. of connected systems, containers and network
namespaces.

.. note:: See also the module choice guide: :ref:`choice`

In a nutshell, NDB collects and aggregates netlink events in an SQL database,
provides Python objects to reflect the system state, and applies changes back
to the system. The database expects updates only from the sources, no manual
SQL updates are expected normally.

.. aafig::
    :scale: 80
    :textual:

        +----------------------------------------------------------------+
      +----------------------------------------------------------------+ |
    +----------------------------------------------------------------+ | |
    |                                                                | | |
    |                              kernel                            | |-+
    |                                                                |-+
    +----------------------------------------------------------------+
            |                      | ^                     | ^
            | `netlink events`     | |                     | |
            | `inotify events`     | |                     | |
            | `...`                | |                     | |
            v                      v |                     v |
     +--------------+        +--------------+        +--------------+
     |     source   |        |     source   |        |     source   |<--\\
     +--------------+        +--------------+        +--------------+   |
            |                       |                       |           |
            |                       |                       |           |
            \\-----------------------+-----------------------/           |
                                    |                                   |
              parsed netlink events | `NDB._event_queue`                |
                                    |                                   |
                                    v                                   |
                        +------------------------+                      |
                        | `NDB.__dbm__()` thread |                      |
                        +------------------------+                      |
                                    |                                   |
                                    v                                   |
                     +-----------------------------+                    |
                     | `NDB.schema.load_netlink()` |                    |
                     | `NDB.objects.*.load*()`     |                    |
                     +-----------------------------+                    |
                                    |                                   |
                                    v                                   |
                         +----------------------+                       |
                         |  SQL database        |                       |
                         |     `SQLite`         |                       |
                         |     `PostgreSQL`     |                       |
                         +----------------------+                       |
                                    |                                   |
                                    |                                   |
                                    V                                   |
                              +---------------+                         |
                            +---------------+ |                         |
                          +---------------+ | |  `RTNL_Object.apply()`  |
                          | NDB object:   | | |-------------------------/
                          |  `interface`  | | |
                          |  `address`    | | |
                          |  `route`      | |-+
                          |  `...`        |-+
                          +---------------+


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
     .commit())
    # ---> <---  NDB waits here for the changes to be applied

    # same as above, but using properties as argument names
    (ndb
     .interfaces['eth0']
     .set(state='up')
     .set(address='00:11:22:33:44:55')
     .commit())

    # ... or with another syntax
    with ndb.interfaces['eth0'] as i:
        i['state'] = 'up'
        i['address'] = '00:11:22:33:44:55'
    # ---> <---  the commit() is called automatically by
    #            the context manager's __exit__()

'''
import atexit
import ctypes
import ctypes.util
import logging
import logging.handlers
import sys
import threading
import time
import traceback
from functools import partial

from pr2modules import config
from pr2modules.common import basestring
from pr2modules.netlink import nlmsg_base

##
# NDB stuff
from . import schema
from .auth_manager import AuthManager
from .events import (
    DBMExitException,
    InvalidateHandlerException,
    RescheduleException,
    ShutdownException,
)
from .messages import cmsg, cmsg_event, cmsg_failed, cmsg_sstart
from .transaction import Transaction
from .view import SourcesView, View

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

try:
    import queue
except ImportError:
    import Queue as queue

log = logging.getLogger(__name__)


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
                handler = logging.handlers.SysLogHandler(
                    address=url.netloc.split(':')
                )
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

    def close(self):
        manager = self.logger.manager
        name = self.logger.name
        # the loggerDict can be huge, so don't
        # cache all the keys -- cache only the
        # needed ones
        purge_list = []
        for logger in manager.loggerDict.keys():
            if logger.startswith(name):
                purge_list.append(logger)
        # now shoot them one by one
        for logger in purge_list:
            del manager.loggerDict[logger]
        # don't force GC, leave it to the user
        del manager
        del name
        del purge_list

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

    def put(self, msg, source=None):
        return self._queue.put((source, msg))

    def shutdown(self):
        self._queue = DeadEnd()

    def bypass(self, msg, source=None):
        return self._bypass.put((source, msg))

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

        for spec in (
            'interfaces',
            'addresses',
            'routes',
            'neighbours',
            'rules',
            'netns',
            'vlans',
        ):
            view = View(self._ndb, spec, auth_managers=self._auth_managers)
            setattr(self, spec, view)


class NDB(object):
    @property
    def nsmanager(self):
        return '%s/nsmanager' % self.localhost

    def __init__(
        self,
        sources=None,
        localhost='localhost',
        db_provider='sqlite3',
        db_spec=':memory:',
        db_cleanup=True,
        rtnl_debug=False,
        log=False,
        auto_netns=False,
        libc=None,
        messenger=None,
    ):

        if db_provider == 'postgres':
            db_provider = 'psycopg2'

        self.localhost = localhost
        self.ctime = self.gctime = time.time()
        self.schema = None
        self.config = {}
        self.libc = libc or ctypes.CDLL(
            ctypes.util.find_library('c'), use_errno=True
        )
        self.log = Log(log_id=id(self))
        self.readonly = ReadOnly(self)
        self._auto_netns = auto_netns
        self._db = None
        self._dbm_thread = None
        self._dbm_ready = threading.Event()
        self._dbm_shutdown = threading.Event()
        self._db_cleanup = db_cleanup
        self._global_lock = threading.Lock()
        self._event_map = None
        self._event_queue = EventQueue(maxsize=100)
        self.messenger = messenger
        if messenger is not None:
            self._mm_thread = threading.Thread(
                target=self.__mm__, name='Messenger'
            )
            self._mm_thread.setDaemon(True)
            self._mm_thread.start()
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
            sources = [
                {'target': self.localhost, 'kind': 'local', 'nlm_generator': 1}
            ]
            if sys.platform.startswith('linux'):
                sources.append({'target': self.nsmanager, 'kind': 'nsmanager'})
        elif not isinstance(sources, (list, tuple)):
            raise ValueError('sources format not supported')

        for spec in sources:
            if 'target' not in spec:
                spec['target'] = self.localhost
                break

        am = AuthManager(
            {'obj:list': True, 'obj:read': True, 'obj:modify': True},
            self.log.channel('auth'),
        )
        self.sources = SourcesView(self, auth_managers=[am])
        self._call_registry = {}
        self._nl = sources
        self._db_provider = db_provider
        self._db_spec = db_spec
        self._db_rtnl_log = rtnl_debug
        atexit.register(self.close)
        self._dbm_ready.clear()
        self._dbm_error = None
        self._dbm_autoload = set()
        self._dbm_thread = threading.Thread(
            target=self.__dbm__, name='NDB main loop'
        )
        self._dbm_thread.daemon = True
        self._dbm_thread.start()
        self._dbm_ready.wait()
        if self._dbm_error is not None:
            raise self._dbm_error
        for event in tuple(self._dbm_autoload):
            event.wait()
        self._dbm_autoload = None
        for spec in (
            ('interfaces', 'interfaces'),
            ('addresses', 'addresses'),
            ('routes', 'routes'),
            ('neighbours', 'neighbours'),
            ('af_bridge_fdb', 'fdb'),
            ('rules', 'rules'),
            ('netns', 'netns'),
            ('af_bridge_vlans', 'vlans'),
        ):
            view = View(self, spec[0], auth_managers=[am])
            setattr(self, spec[1], view)
        # self.query = Query(self.schema)

    def _get_view(self, name, chain=None):
        return View(self, name, chain)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def begin(self):
        return Transaction(self.log.channel('transaction'))

    def auth_proxy(self, auth_manager):
        return AuthProxy(self, [auth_manager])

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
            self._event_queue.bypass((cmsg(None, ShutdownException()),))
            self._dbm_thread.join()
            # shutdown the logger -- free the resources
            self.log.close()

    def backup(self, spec):
        self.schema.backup(spec)

    def reload(self, kinds=None):
        for source in self.sources.values():
            if kinds is not None and source.kind in kinds:
                source.restart()

    def __mm__(self):
        # notify neighbours by sending hello
        for peer in self.messenger.transport.peers:
            peer.hello()
        # receive events
        for msg in self.messenger:
            if msg['type'] == 'system' and msg['data'] == 'HELLO':
                for peer in self.messenger.transport.peers:
                    peer.last_exception_time = 0
                self.reload(kinds=['local', 'netns', 'remote'])
            elif msg['type'] == 'transport':
                message = msg['data'][0](data=msg['data'][1])
                message.decode()
                message['header']['target'] = msg['target']
                self._event_queue.put((message,))
            elif msg['type'] == 'response':
                if msg['call_id'] in self._call_registry:
                    event = self._call_registry.pop(msg['call_id'])
                    self._call_registry[msg['call_id']] = msg
                    event.set()
            elif msg['type'] == 'api':
                if msg['target'] in self.messenger.targets:
                    try:
                        ret = self.sources[msg['target']].api(
                            msg['name'], *msg['argv'], **msg['kwarg']
                        )
                        self.messenger.emit(
                            {
                                'type': 'response',
                                'call_id': msg['call_id'],
                                'return': ret,
                            }
                        )
                    except Exception as e:
                        self.messenger.emit(
                            {
                                'type': 'response',
                                'call_id': msg['call_id'],
                                'exception': e,
                            }
                        )
            else:
                self.log.warning('unknown protocol via messenger')

    def __dbm__(self):
        def default_handler(target, event):
            if isinstance(getattr(event, 'payload', None), Exception):
                raise event.payload
            log.debug('unsupported event ignored: %s' % type(event))

        def check_sources_started(self, _locals, target, event):
            _locals['countdown'] -= 1
            if _locals['countdown'] == 0:
                self._dbm_ready.set()

        _locals = {'countdown': len(self._nl)}

        # init the events map
        event_map = {
            cmsg_event: [lambda t, x: x.payload.set()],
            cmsg_failed: [lambda t, x: (self.schema.mark(t, 1))],
            cmsg_sstart: [partial(check_sources_started, self, _locals)],
        }
        self._event_map = event_map

        event_queue = self._event_queue

        try:
            dbconfig = schema.DBConfig()
            dbconfig.provider = schema.DBProvider(self._db_provider)
            dbconfig.spec = self._db_spec
            self.schema = schema.DBSchema(
                dbconfig,
                self,
                self._event_queue,
                self._event_map,
                self._db_rtnl_log,
                self.log.channel('schema'),
            )

        except Exception as e:
            self._dbm_error = e
            self._dbm_ready.set()
            return

        for spec in self._nl:
            spec['event'] = None
            self.sources.add(**spec)

        for (event, handlers) in self.schema.event_map.items():
            for handler in handlers:
                self.register_handler(event, handler)

        stop = False
        source = None
        reschedule = []
        while not stop:
            source, events = event_queue.get()
            events = Events(events, reschedule)
            reschedule = []
            try:
                for event in events:
                    handlers = event_map.get(
                        event.__class__, [default_handler]
                    )
                    if self.messenger is not None and (
                        event.get('header', {}).get('target', None)
                        in self.messenger.targets
                    ):
                        if isinstance(event, nlmsg_base):
                            if event.data is not None:
                                data = event.data[
                                    event.offset : event.offset + event.length
                                ]
                            else:
                                event.reset()
                                event.encode()
                                data = event.data
                            data = (type(event), data)
                            tgt = event['header']['target']
                            self.messenger.emit(
                                {
                                    'type': 'transport',
                                    'target': tgt,
                                    'data': data,
                                }
                            )

                    for handler in tuple(handlers):
                        try:
                            target = event['header']['target']
                            handler(target, event)
                        except RescheduleException:
                            if 'rcounter' not in event['header']:
                                event['header']['rcounter'] = 0
                            if event['header']['rcounter'] < 3:
                                event['header']['rcounter'] += 1
                                self.log.debug('reschedule %s' % (event,))
                                reschedule.append(event)
                            else:
                                self.log.error('drop %s' % (event,))
                        except InvalidateHandlerException:
                            try:
                                handlers.remove(handler)
                            except Exception:
                                self.log.error(
                                    'could not invalidate '
                                    'event handler:\n%s'
                                    % traceback.format_exc()
                                )
                        except ShutdownException:
                            stop = True
                            break
                        except DBMExitException:
                            return
                        except Exception:
                            self.log.error(
                                'could not load event:\n%s\n%s'
                                % (event, traceback.format_exc())
                            )
                    if time.time() - self.gctime > config.gc_timeout:
                        self.gctime = time.time()
            except Exception as e:
                self.log.error(f'exception <{e}> in source {source}')
                # restart the target
                try:
                    self.log.debug(f'requesting source {source} restart')
                    self.sources[source].state.set('restart')
                except KeyError:
                    self.log.debug(f'key error for {source}')
                    pass

        # release all the sources
        for target in tuple(self.sources.cache):
            source = self.sources.remove(target, sync=False)
            if source is not None and source.th is not None:
                source.shutdown.set()
                source.th.join()
                if self._db_cleanup:
                    self.log.debug('flush DB for the target %s' % target)
                    self.schema.flush(target)
                else:
                    self.log.debug('leave DB for debug')

        # close the database
        self.schema.commit()
        self.schema.close()

        # close the logging
        for handler in self.log.logger.handlers:
            handler.close()
