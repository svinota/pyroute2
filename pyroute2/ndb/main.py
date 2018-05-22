#
# NDB is NOT a production but a proof-of-concept
#
# It is intended to become IPDB version 2.0 that can handle
# thousands network objects -- something that IPDB can not
# due to memory consupmtion
#

import logging
import threading
from pyroute2 import IPRoute
from pyroute2.ndb import interfaces
try:
    import queue
except ImportError:
    import Queue as queue  # The module is called 'Queue' in Python2

plugins = [interfaces, ]


class ShutdownException(Exception):
    pass


class NDB(object):

    def __init__(self, nl=None):

        self._dbm_thread = None
        self._event_queue = None
        self._nl_own = nl is None

        ipr = IPRoute()
        ipr.bind()
        self.nl = {'localhost': ipr}

        # channels to OS
        # self.nl = nl if isinstance(nl, dict) else {"localhost": nl}
        # monitoring channels
        # self.mnl = {}

        self.initdb()

    def initdb(self):
        # stop DBM if exists
        if self._dbm_thread is not None:
            self._event_queue.put(ShutdownException("restart NDB"))
            self._dbm_thread.join()
        self._dbm_thread = threading.Thread(target=self.__dbm__,
                                            name='NDB main loop')
        self._dbm_thread.setDaemon(True)
        self._dbm_thread.start()

    def __dbm__(self):
        ##
        # Database management thread
        ##
        global plugins
        event_map = {}
        self._event_queue = event_queue = queue.Queue()

        def default_handler(event):
            if isinstance(event, Exception):
                raise event
            logging.warning('unsupported event ignored: %s' % type(event))

        for plugin in plugins:
            plugin.thread = threading.current_thread()
            plugin.db = plugin.createdb()
            for (event, handler) in plugin.event_map.items():
                if event not in event_map:
                    event_map[event] = []
                event_map[event].append(handler)

        for (target, channel) in tuple(self.nl.items()):
            # an instance must support register_evq()
            def t():
                while True:
                    event_queue.put(channel.get())

            th = threading.Thread(target=t,
                                  name='NDB event source: %s' % (target))
            th.setDaemon(True)
            th.start()

        while True:
            events = event_queue.get()
            for event in events:
                handlers = event_map.get(event.__class__, [default_handler, ])
                for handler in handlers:
                    try:
                        handler(event)
                    except:
                        import traceback
                        traceback.print_exc()
