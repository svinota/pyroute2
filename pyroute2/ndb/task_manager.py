import asyncio
import logging
import threading
import time
import traceback

from pyroute2 import config

from . import schema
from .events import (
    DBMExitException,
    InvalidateHandlerException,
    RescheduleException,
    ShutdownException,
)
from .messages import cmsg_event, cmsg_failed

log = logging.getLogger(__name__)


class NDBConfig(dict):
    def __init__(self, task_manager):
        self.task_manager = task_manager

    def __getitem__(self, key):
        return self.task_manager.config_get(key)

    def __setitem__(self, key, value):
        return self.task_manager.config_set(key, value)

    def __delitem__(self, key):
        return self.task_manager.config_del(key)

    def keys(self):
        return self.task_manager.config_keys()

    def items(self):
        return self.task_manager.config_items()

    def values(self):
        return self.task_manager.config_values()


class TaskManager:
    def __init__(self, ndb):
        self.ndb = ndb
        self.log = ndb.log
        self.event_map = {}
        self.task_map = {}
        self.event_queue = (
            asyncio.Queue()
        )  # LoggingQueue(log=self.ndb.log.channel('queue'))
        self.stop_event = asyncio.Event()
        self.reload_event = asyncio.Event()
        self.thread = None
        self.ctime = self.gctime = time.time()
        self.ready = asyncio.Event()

    def register_handler(self, event, handler):
        if event not in self.event_map:
            self.event_map[event] = []
        self.event_map[event].append(handler)

    def unregister_handler(self, event, handler):
        self.event_map[event].remove(handler)

    async def handler_default(self, sources, target, event):
        if isinstance(getattr(event, 'payload', None), Exception):
            raise event.payload
        log.debug('unsupported event ignored: %s' % type(event))

    async def handler_event(self, sources, target, event):
        event.payload.set()

    async def handler_failed(self, sources, target, event):
        self.ndb.schema.mark(target, 1)

    def main(self):
        asyncio.run(self.run())

    def create_task(self, coro, state='running'):
        task = asyncio.create_task(coro())
        self.task_map[task] = [state, coro]
        self.reload_event.set()
        return task

    async def stop(self):
        await self.stop_event.wait()

    async def reload(self):
        await self.reload_event.wait()

    async def task_watch(self):
        while True:
            tasks = list(self.task_map.keys())
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            self.log.debug(f'task done {done}')
            if self.stop_event.is_set():
                return
            for task in done:
                if task.exception():
                    self.log.debug(f'task exception {task.exception()}')
                target_state, init = self.task_map.pop(task)
                if target_state == 'running':
                    self.create_task(init)
            self.reload_event.clear()

    async def receiver(self):
        while True:
            event = await self.event_queue.get()
            reschedule = []
            handlers = self.event_map.get(
                event.__class__, [self.handler_default]
            )

            for handler in tuple(handlers):
                try:
                    target = event['header']['target']
                    # self.log.debug(f'await {handler} for {event}')
                    await handler(self.ndb.sources.asyncore, target, event)
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
                            'event handler:\n%s' % traceback.format_exc()
                        )
                except ShutdownException:
                    return
                except DBMExitException:
                    return
                except Exception:
                    self.log.error(
                        'could not load event:\n%s\n%s'
                        % (event, traceback.format_exc())
                    )
            if time.time() - self.gctime > config.gc_timeout:
                self.gctime = time.time()

    async def run(self):
        self.thread = id(threading.current_thread())

        # init the events map
        event_map = {
            cmsg_event: [self.handler_event],
            cmsg_failed: [self.handler_failed],
        }
        self.event_map = event_map

        try:
            self.ndb.schema = schema.DBSchema(
                self.ndb.config, self.event_map, self.log.channel('schema')
            )
            self.ndb.config = NDBConfig(self)

        except Exception as e:
            self.ndb._dbm_error = e
            self.ready.set()
            return

        for event, handlers in self.ndb.schema.event_map.items():
            for handler in handlers:
                self.register_handler(event, handler)

        # create an event loop
        self.event_loop = asyncio.get_event_loop()
        self.ndb.event_loop = self.event_loop
        self.create_task(self.receiver)
        self.create_task(self.stop)
        self.create_task(self.reload)
        self.ndb._dbm_ready.set()
        await self.task_watch()
        self.ndb.schema.close()
        self.ndb._dbm_shutdown.set()
        self.ready.set()
