import time
import logging
import threading
from pyroute2 import IPRoute
from pyroute2 import RemoteIPRoute
from pyroute2.netns.nslink import NetNS
from pyroute2.ndb.events import (SyncStart,
                                 SchemaReadLock,
                                 SchemaReadUnlock,
                                 MarkFailed,
                                 State,
                                 Log)
from pyroute2.netlink.nlsocket import NetlinkMixin
from pyroute2.netlink.exceptions import NetlinkError

log = logging.getLogger(__name__)
SOURCE_FAIL_PAUSE = 5


class Source(dict):
    '''
    The RNTL source. The source that is used to init the object
    must comply to IPRoute API, must support the async_cache. If
    the source starts additional threads, they must be joined
    in the source.close()
    '''
    table_alias = 'src'
    dump = None
    dump_header = None
    summary = None
    summary_header = None
    view = None
    table = 'sources'
    vmap = {'local': IPRoute,
            'netns': NetNS,
            'remote': RemoteIPRoute}

    def __init__(self, ndb, **spec):
        self.th = None
        self.nl = None
        self.ndb = ndb
        self.evq = self.ndb._event_queue
        # the target id -- just in case
        self.target = spec.pop('target')
        kind = spec.pop('kind', 'local')
        self.persistent = spec.pop('persistent', True)
        self.event = spec.pop('event')
        if not self.event:
            self.event = SyncStart()
        # RTNL API
        self.nl_prime = self.vmap[kind]
        self.nl_kwarg = spec
        #
        self.shutdown = threading.Event()
        self.started = threading.Event()
        self.lock = threading.RLock()
        self.started.clear()
        self.state = State()
        self.log = Log()
        self.state.set('init')
        self.ndb.schema.execute('''
                                INSERT INTO sources (f_target, f_kind)
                                VALUES (%s, %s)
                                ''' % (self.ndb.schema.plch,
                                       self.ndb.schema.plch),
                                (self.target, kind))
        for key, value in spec.items():
            vtype = 'int' if isinstance(value, int) else 'str'
            self.ndb.schema.execute('''
                                    INSERT INTO options (f_target,
                                                         f_name,
                                                         f_type,
                                                         f_value)
                                    VALUES (%s, %s, %s, %s)
                                    ''' % (self.ndb.schema.plch,
                                           self.ndb.schema.plch,
                                           self.ndb.schema.plch,
                                           self.ndb.schema.plch),
                                    (self.target, key, vtype, value))

        self.load_sql()

    def remove(self):
        with self.lock:
            self.close()
            (self
             .ndb
             .schema
             .execute('''
                      DELETE FROM sources WHERE f_target=%s
                      ''' % self.ndb.schema.plch, (self.target, )))
            (self
             .ndb
             .schema
             .execute('''
                      DELETE FROM options WHERE f_target=%s
                      ''' % self.ndb.schema.plch, (self.target, )))
            return self

    def __repr__(self):
        if isinstance(self.nl_prime, NetlinkMixin):
            name = self.nl_prime.__class__.__name__
        elif isinstance(self.nl_prime, type):
            name = self.nl_prime.__name__

        return '[%s] <%s %s>' % (self.state.get(), name, self.nl_kwarg)

    @classmethod
    def nla2name(cls, name):
        return name

    @classmethod
    def name2nla(cls, name):
        return name

    def api(self, name, *argv, **kwarg):
        for _ in range(100):  # FIXME make a constant
            with self.lock:
                try:
                    return getattr(self.nl, name)(*argv, **kwarg)
                except (NetlinkError,
                        AttributeError,
                        ValueError,
                        KeyError):
                    raise
                except Exception as e:
                    # probably the source is restarting
                    log.debug('[%s] source api error: %s' %
                              (self.target, e))
                    time.sleep(1)
        raise RuntimeError('api call failed')

    def receiver(self):
        #
        # The source thread routine -- get events from the
        # channel and forward them into the common event queue
        #
        # The routine exists on an event with error code == 104
        #
        while True:
            with self.lock:
                if self.shutdown.is_set():
                    log.debug('[%s] stopped' % self.target)
                    self.state.set('stopped')
                    return

                if self.nl is not None:
                    try:
                        self.nl.close(code=0)
                    except Exception as e:
                        self.log.append('restarting the nl transport')
                        log.warning('[%s] source restart: %s'
                                    % (self.target, e))
                try:
                    self.log.append('connecting')
                    log.debug('[%s] connecting' % self.target)
                    self.state.set('connecting')
                    if isinstance(self.nl_prime, type):
                        self.nl = self.nl_prime(**self.nl_kwarg)
                    else:
                        raise TypeError('source channel not supported')
                    self.log.append('loading')
                    log.debug('[%s] loading' % self.target)
                    self.state.set('loading')
                    #
                    self.nl.bind(async_cache=True, clone_socket=True)
                    #
                    # Initial load -- enqueue the data
                    #
                    self.ndb.schema.allow_read(False)
                    try:
                        self.ndb.schema.flush(self.target)
                        self.evq.put((self.target, self.nl.get_links()))
                        self.evq.put((self.target, self.nl.get_addr()))
                        self.evq.put((self.target, self.nl.get_neighbours()))
                        self.evq.put((self.target, self.nl.get_routes()))
                    finally:
                        self.ndb.schema.allow_read(True)
                    self.started.set()
                    self.shutdown.clear()
                    self.log.append('running')
                    log.debug('[%s] running' % self.target)
                    self.state.set('running')
                    if self.event is not None:
                        self.evq.put((self.target, (self.event, )))
                except TypeError:
                    raise
                except Exception as e:
                    self.started.set()
                    self.log.append('failed')
                    log.debug('[%s] failed' % self.target)
                    self.state.set('failed')
                    log.error('[%s] source error: %s %s' %
                              (self.target, type(e), e))
                    self.evq.put((self.target, (MarkFailed(), )))
                    if self.persistent:
                        self.log.append('sleeping before restart')
                        log.debug('[%s] sleeping before restart' % self.target)
                        self.shutdown.wait(SOURCE_FAIL_PAUSE)
                        if self.shutdown.is_set():
                            self.log.append('source shutdown')
                            log.debug('[%s] source shutdown' % self.target)
                            return
                    else:
                        return
                    continue

            while True:
                try:
                    msg = tuple(self.nl.get())
                except Exception as e:
                    self.log.append('error: %s %s' % (type(e), e))
                    log.error('[%s] source error: %s %s' %
                              (self.target, type(e), e))
                    msg = None
                    if self.persistent:
                        break

                if msg is None or \
                        msg[0]['header']['error'] and \
                        msg[0]['header']['error'].code == 104:
                    self.log.append('stopped')
                    log.debug('[%s] stopped' % self.target)
                    self.state.set('stopped')
                    # thus we make sure that all the events from
                    # this source are consumed by the main loop
                    # in __dbm__() routine
                    sync = threading.Event()
                    self.evq.put((self.target, (sync, )))
                    sync.wait()
                    return

                self.ndb.schema._allow_write.wait()
                self.evq.put((self.target, msg))

    def start(self):

        #
        # Start source thread
        with self.lock:
            self.log.append('starting the source')
            if (self.th is not None) and self.th.is_alive():
                raise RuntimeError('source is running')

            self.th = (threading
                       .Thread(target=self.receiver,
                               name='NDB event source: %s' % (self.target)))
            self.th.start()
            return self

    def close(self):
        with self.lock:
            self.log.append('stopping the source')
            self.shutdown.set()
            if self.nl is not None:
                try:
                    self.nl.close()
                except Exception as e:
                    log.error('[%s] source close: %s' % (self.target, e))
        if self.th is not None:
            self.th.join()
        self.log.append('flushing the DB for the target')
        self.ndb.schema.flush(self.target)

    def restart(self):
        with self.lock:
            if not self.shutdown.is_set():
                self.log.append('restarting the source')
                self.evq.put((self.target, (SchemaReadLock(), )))
                try:
                    self.close()
                    self.start()
                finally:
                    self.evq.put((self.target, (SchemaReadUnlock(), )))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def load_sql(self):
        #
        spec = self.ndb.schema.fetchone('''
                                        SELECT * FROM sources
                                        WHERE f_target = %s
                                        ''' % self.ndb.schema.plch,
                                        (self.target, ))
        self['target'], self['kind'] = spec
        for spec in self.ndb.schema.fetch('''
                                          SELECT * FROM options
                                          WHERE f_target = %s
                                          ''' % self.ndb.schema.plch,
                                          (self.target, )):
            f_target, f_name, f_type, f_value = spec
            self[f_name] = int(f_value) if f_type == 'int' else f_value
