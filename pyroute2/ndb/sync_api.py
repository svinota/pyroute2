import asyncio
from queue import Queue
from typing import AsyncGenerator, Callable, TypeAlias

from .report import RecordSet

Req: TypeAlias = dict[str, str | int]


class Sync_Base:

    def __init__(self, event_loop, obj):
        self.event_loop = event_loop
        self.obj = obj


class Sync_Object(Sync_Base):

    def apply(
        self,
        rollback: bool = False,
        req_filter: None | Callable[[Req], Req] = None,
        mode: str = 'apply',
    ) -> Sync_Base:
        task = asyncio.run_coroutine_threadsafe(
            self.obj.apply(rollback, req_filter, mode), self.event_loop
        )
        return self

    def commit(self) -> Sync_Base:
        task = asyncio.run_coroutine_threadsafe(
            self.obj.commit(), self.event_loop
        )
        return self

    def __repr__(self):
        return repr(self.obj)


class Sync_View:

    def __init__(self, event_loop, obj):
        self.event_loop = event_loop
        self.obj = obj
        self.queue = Queue()

    async def _async_generator(self, func):
        for record in func():
            self.queue.put(record)
        self.queue.put(None)

    def _sync_generator(self, func: AsyncGenerator):
        task = asyncio.run_coroutine_threadsafe(
            self._async_generator(func), self.event_loop
        )
        while True:
            record = self.queue.get()
            if record is None:
                return
            yield record
        ret = task.result()
        if isinstance(ret, Exception):
            raise ret

    async def _async_call(self, func, *argv, **kwarg):
        return func(*argv, **kwarg)

    def _sync_call(self, func, *argv, **kwarg):
        task = asyncio.run_coroutine_threadsafe(
            self._async_call(func, *argv, **kwarg), self.event_loop
        )
        return task.result()

    def __getitem__(self, key, table=None):
        item = self._sync_call(self.obj.__getitem__, key, table)
        return Sync_Object(self.event_loop, item)

    def create(self, *argspec, **kwarg):
        item = self._sync_call(self.obj.create, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def ensure(self, *argspec, **kwarg):
        item = self._sync_call(self.obj.ensure, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def add(self, *argspec, **kwarg):
        item = self._sync_call(self.obj.add, *argspec, **kwarg)
        return Sync_Object(self.event_loop, item)

    def wait(self, **spec):
        item = self._sync_call(self.obj.wait, **spec)
        return Sync_Object(self.event_loop, item)

    def exists(self, key, table=None):
        return self._sync_call(self.obj.exists, key, table)

    def locate(self, spec=None, table=None, **kwarg):
        item = self._sync_call(self.obj.locate, spec, table, **kwarg)
        return Sync_Object(self.event_loop, item)

    def summary(self):
        return RecordSet(self._sync_generator(self.obj.summary))

    def dump(self):
        return RecordSet(self._sync_generator(self.obj.dump))
