#
# NDB is NOT a production but a proof-of-concept
#
# It is intended to become IPDB version 2.0 that can handle
# thousands of network objects -- something that IPDB can not
# due to memory consupmtion
#
#
# Proposed design:
#
# 0. multiple event sources -- IPRoute (Linux), RTMSocket (BSD), etc
# 1. the main loop dispatches incoming events to plugins
# 2. plugins store serialized events as records in an internal DB (SQL)
# 3. plugins provide an API to access records as Python objects
# 4. objects are spawned only on demand
# 5. plugins provide transactional API to change objects + OS reflection
import os
import json
import select
import sqlite3
import logging
import threading
from socket import AF_INET
from socket import AF_INET6
from pyroute2 import IPRoute
from pyroute2.ndb import dbschema
from pyroute2.common import AF_MPLS
try:
    import queue
except ImportError:
    import Queue as queue


def target_adapter(value):
    return json.dumps(value)


sqlite3.register_adapter(list, target_adapter)


class ShutdownException(Exception):
    pass


class NDB(object):

    def __init__(self, nl=None, db_uri=':memory:'):

        self.db = None
        self.dbschema = None
        self._dbm_thread = None
        self._dbm_ready = threading.Event()
        self._global_lock = threading.Lock()
        self._event_queue = queue.Queue()
        self._nl = nl
        self._db_uri = db_uri
        self._control_channels = []
        self._src_threads = []
        self._dbm_ready.clear()
        self._dbm_thread = threading.Thread(target=self.__dbm__,
                                            name='NDB main loop')
        self._dbm_thread.start()

    def close(self):
        with self._global_lock:
            if self.db:
                self._event_queue.put(('localhost', (ShutdownException(), )))
                self.db.commit()
                self.db.close()
                for (ctlr, ctlw) in self._control_channels:
                    os.write(ctlw, b'\0')
                    os.close(ctlw)
                    os.close(ctlr)
                for (target, channel) in self.nl.items():
                    channel.close()
                self.control_channels = []
                for src in self._src_threads:
                    src.join()
                self._dbm_thread.join()

    def __initdb__(self):
        with self._global_lock:
            #
            # stop running sources, if any
            if self._control_channels:
                for (ctlr, ctlw) in self._control_channels:
                    os.write(ctlw, b'\0')
                    os.close(ctlw)
                    os.close(ctlr)
                for src in self._src_threads:
                    src.join()
                self._control_channels = []
                self._src_threads = []
            #
            # start event sockets
            if self._nl is None:
                ipr = IPRoute()
                self.nl = {'localhost': ipr}
            elif isinstance(self._nl, dict):
                self.nl = dict([(x[0], x[1].clone()) for x
                                in self._nl.items()])
            else:
                self.nl = {'localhost': self._nl.clone()}
            for target in self.nl:
                self.nl[target].bind()
            #
            # close the current db
            if self.db:
                self.db.commit()
                self.db.close()
            #
            # ACHTUNG!
            # check_same_thread=False
            #
            # Do NOT write into the DB from ANY other thread
            # than self._dbm_thread!
            #
            self.db = sqlite3.connect(self._db_uri, check_same_thread=False)
            if self.dbschema:
                self.dbschema.db = self.db
            #
            # initial load
            evq = self._event_queue
            for (target, channel) in tuple(self.nl.items()):
                evq.put((target, channel.get_links()))
                evq.put((target, channel.get_neighbours()))
                evq.put((target, channel.get_routes(family=AF_INET)))
                evq.put((target, channel.get_routes(family=AF_INET6)))
                evq.put((target, channel.get_routes(family=AF_MPLS)))
                evq.put((target, channel.get_addr()))
            evq.put(('localhost', (self._dbm_ready, ), ))
            #
            # start source threads
            for (target, channel) in tuple(self.nl.items()):
                ctlr, ctlw = os.pipe()
                self._control_channels.append((ctlr, ctlw))

                def t(event_queue, target, channel, control):
                    ins = [channel.fileno(), control]
                    outs = []
                    while True:
                        try:
                            events, _, _ = select.select(ins, outs, ins)
                        except:
                            continue
                        for fd in events:
                            if fd == control:
                                return
                            else:
                                event_queue.put((target, channel.get()))

                th = threading.Thread(target=t,
                                      args=(self._event_queue,
                                            target,
                                            channel,
                                            ctlr),
                                      name='NDB event source: %s' % (target))
                th.start()
                self._src_threads.append(th)

    def __dbm__(self):

        # init the events map
        event_map = {type(self._dbm_ready): [lambda t, x: x.set()]}
        event_queue = self._event_queue

        def default_handler(target, event):
            if isinstance(event, Exception):
                raise event
            logging.warning('unsupported event ignored: %s' % type(event))

        self.__initdb__()

        self.dbschema = dbschema.init(self.db, id(threading.current_thread()))
        for (event, handler) in self.dbschema.event_map.items():
            if event not in event_map:
                event_map[event] = []
            event_map[event].append(handler)

        while True:
            target, events = event_queue.get()
            for event in events:
                handlers = event_map.get(event.__class__, [default_handler, ])
                for handler in handlers:
                    try:
                        handler(target, event)
                    except ShutdownException:
                        return
                    except:
                        import traceback
                        traceback.print_exc()
