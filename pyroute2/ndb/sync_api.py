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
        print(task.result)
        return self

    def commit(self) -> Sync_Base:
        task = asyncio.run_coroutine_threadsafe(
            self.obj.commit(), self.event_loop
        )
        print(task.result)
        return self


class Sync_View:

    def __init__(self, event_loop, obj):
        self.event_loop = event_loop
        self.obj = obj
        self.queue = Queue()

    async def _async_transmitter(self, func):
        for record in func():
            self.queue.put(record)
        self.queue.put(None)

    def _sync_receiver(self, func: AsyncGenerator):
        task = asyncio.run_coroutine_threadsafe(
            self._async_transmitter(func), self.event_loop
        )
        while True:
            record = self.queue.get()
            if record is None:
                return
            yield record
        ret = task.result()
        if isinstance(ret, Exception):
            raise ret

    def summary(self):
        return RecordSet(self._sync_receiver(self.obj.summary))

    def dump(self):
        return RecordSet(self._sync_receiver(self.obj.dump))
