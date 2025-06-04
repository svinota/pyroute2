import asyncio
from queue import Queue
from typing import AsyncGenerator, Callable, TypeAlias

from .report import RecordSet

Req: TypeAlias = dict[str, str | int]


class Sync_Base:

    def __init__(self, event_loop, obj):
        self.event_loop = event_loop
        self.obj = obj
        self.queue = Queue()

    async def _tm_sync_generator(self, func):
        for record in func():
            self.queue.put(record)
        self.queue.put(None)

    def _main_sync_generator(self, func: AsyncGenerator):
        task = asyncio.run_coroutine_threadsafe(
            self._tm_sync_generator(func), self.event_loop
        )
        while True:
            record = self.queue.get()
            if record is None:
                return
            yield record
        ret = task.result()
        if isinstance(ret, Exception):
            raise ret

    async def _tm_sync_call(self, func, *argv, **kwarg):
        return func(*argv, **kwarg)

    def _main_sync_call(self, func, *argv, **kwarg):
        task = asyncio.run_coroutine_threadsafe(
            self._tm_sync_call(func, *argv, **kwarg), self.event_loop
        )
        return task.result()

    def _main_async_call(self, func, *argv, **kwarg):
        task = asyncio.run_coroutine_threadsafe(
            func(*argv, **kwarg), self.event_loop
        )
        return task.result()


class Sync_Object(Sync_Base):

    def apply(
        self,
        rollback: bool = False,
        req_filter: None | Callable[[Req], Req] = None,
        mode: str = 'apply',
    ) -> Sync_Base:
        self._main_async_call(self.obj.commit, rollback, req_filter, mode)
        return self

    def commit(self) -> Sync_Base:
        self._main_async_call(self.obj.commit)
        return self

    def __repr__(self):
        return repr(self.obj)

    def __getitem__(self, key):
        return self.obj[key]


class Sync_View(Sync_Base):

    def __getitem__(self, key, table=None):
        item = self._sync_call(self.obj.__getitem__, key, table)
        return Sync_Object(self.event_loop, item)

    def create(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.create, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def ensure(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.ensure, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def add(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.add, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def wait(self, **spec):
        item = self._main_sync_call(self.obj.wait, **spec)
        return Sync_Object(self.event_loop, item)

    def exists(self, key, table=None):
        return self._main_sync_call(self.obj.exists, key, table)

    def locate(self, spec=None, table=None, **kwarg):
        item = self._main_sync_call(self.obj.locate, spec, table, **kwarg)
        return Sync_Object(self.event_loop, item)

    def summary(self):
        return RecordSet(self._main_sync_generator(self.obj.summary))

    def dump(self):
        return RecordSet(self._main_sync_generator(self.obj.dump))
