import time
import logging
import threading
from pyroute2.ndb.events import (SchemaFlush,
                                 MarkFailed)
from pyroute2.netlink.nlsocket import NetlinkMixin
from pyroute2.netlink.exceptions import NetlinkError

log = logging.getLogger(__name__)
SOURCE_FAIL_PAUSE = 5


class Source(object):
    '''
    The RNTL source. The source that is used to init the object
    must comply to IPRoute API, must support the async_cache. If
    the source starts additional threads, they must be joined
    in the source.close()
    '''

    def __init__(self, evq, target, source,
                 event=None,
                 persistent=True,
                 **nl_kwarg):
        self.th = None
        self.nl = None
        # the event queue to send events to
        self.evq = evq
        # the target id -- just in case
        self.target = target
        # RTNL API
        self.nl_prime = source
        self.nl_kwarg = nl_kwarg
        #
        self.event = event
        self.shutdown = threading.Event()
        self.started = threading.Event()
        self.lock = threading.Lock()
        self.started.clear()
        self.persistent = persistent
        self.state = 'init'

    def __repr__(self):
        if isinstance(self.nl_prime, NetlinkMixin):
            name = self.nl_prime.__class__.__name__
        elif isinstance(self.nl_prime, type):
            name = self.nl_prime.__name__

        return '[%s] <%s %s>' % (self.state, name, self.nl_kwarg)

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
                    self.state = 'stopped'
                    return

                if self.nl is not None:
                    try:
                        self.nl.close(code=0)
                    except Exception as e:
                        log.warning('[%s] source restart: %s'
                                    % (self.target, e))
                try:
                    log.debug('[%s] connecting' % self.target)
                    self.state = 'connecting'
                    if isinstance(self.nl_prime, NetlinkMixin):
                        self.nl = self.nl_prime
                    elif isinstance(self.nl_prime, type):
                        self.nl = self.nl_prime(**self.nl_kwarg)
                    else:
                        raise TypeError('source channel not supported')
                    log.debug('[%s] loading' % self.target)
                    self.state = 'loading'
                    #
                    self.nl.bind(async_cache=True, clone_socket=True)
                    #
                    # Initial load -- enqueue the data
                    #
                    self.evq.put((self.target, (SchemaFlush(), )))
                    self.evq.put((self.target, self.nl.get_links()))
                    self.evq.put((self.target, self.nl.get_addr()))
                    self.evq.put((self.target, self.nl.get_neighbours()))
                    self.evq.put((self.target, self.nl.get_routes()))
                    self.started.set()
                    self.shutdown.clear()
                    log.debug('[%s] running' % self.target)
                    self.state = 'running'
                    if self.event is not None:
                        self.evq.put((self.target, (self.event, )))
                except TypeError:
                    raise
                except Exception as e:
                    self.started.set()
                    log.debug('[%s] failed' % self.target)
                    self.state = 'failed'
                    log.error('[%s] source error: %s %s' %
                              (self.target, type(e), e))
                    self.evq.put((self.target, (MarkFailed(), )))
                    if self.persistent:
                        log.debug('[%s] sleeping before restart' % self.target)
                        self.shutdown.wait(SOURCE_FAIL_PAUSE)
                        if self.shutdown.is_set():
                            log.debug('[%s] source shutdown' % self.target)
                            return
                    else:
                        return
                    continue

            while True:
                try:
                    msg = tuple(self.nl.get())
                except Exception as e:
                    log.error('[%s] source error: %s %s' %
                              (self.target, type(e), e))
                    msg = None
                    if self.persistent:
                        break

                if msg is None or \
                        msg[0]['header']['error'] and \
                        msg[0]['header']['error'].code == 104:
                    log.debug('[%s] stopped' % self.target)
                    self.state = 'stopped'
                    # thus we make sure that all the events from
                    # this source are consumed by the main loop
                    # in __dbm__() routine
                    sync = threading.Event()
                    self.evq.put((self.target, (sync, )))
                    sync.wait()
                    return

                self.evq.put((self.target, msg))

    def start(self):

        #
        # Start source thread
        with self.lock:
            if (self.th is not None) and self.th.is_alive():
                raise RuntimeError('source is running')

            self.th = (threading
                       .Thread(target=self.receiver,
                               name='NDB event source: %s' % (self.target)))
            self.th.start()

    def close(self):
        with self.lock:
            self.shutdown.set()
            if self.nl is not None:
                try:
                    self.nl.close()
                except Exception as e:
                    log.error('[%s] source close: %s' % (self.target, e))
        if self.th is not None:
            self.th.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
