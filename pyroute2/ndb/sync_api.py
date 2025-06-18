import asyncio
import errno
from queue import Queue
from typing import AsyncGenerator, Callable, TypeAlias

from .report import RecordSet

Req: TypeAlias = dict[str, str | int]


class Sync_Base:

    def __init__(self, event_loop, obj):
        self.event_loop = event_loop
        self.obj = obj
        self.queue = Queue()

    async def _tm_sync_generator(self, func, *argv, **kwarg):
        for record in func(*argv, **kwarg):
            self.queue.put(record)
        self.queue.put(None)

    def _main_sync_generator(self, func, *argv, **kwarg):
        task = asyncio.run_coroutine_threadsafe(
            self._tm_sync_generator(func, *argv, **kwarg), self.event_loop
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
        ret = task.result()
        if isinstance(ret, Exception):
            raise ret
        return ret

    def _main_async_call(self, func, *argv, **kwarg):
        task = asyncio.run_coroutine_threadsafe(
            func(*argv, **kwarg), self.event_loop
        )
        ret = task.result()
        if isinstance(ret, Exception):
            raise ret
        return ret


class Sync_Object(Sync_Base):

    def apply(
        self,
        rollback: bool = False,
        req_filter: None | Callable[[Req], Req] = None,
        mode: str = 'apply',
    ) -> Sync_Base:
        self._main_async_call(self.obj.commit, rollback, req_filter, mode)
        return self

    @property
    def state(self):
        return self.obj.state

    @property
    def chain(self):
        return type(self)(self.event_loop, self.obj.chain)

    def commit(self) -> Sync_Base:
        self._main_async_call(self.obj.commit)
        return self

    def rollback(self, snapshot=None):
        self._main_async_call(self.obj.rollback, snapshot)
        return self

    def show(self, fmt=None):
        return self.obj.show(fmt)

    def keys(self):
        return self.obj.keys()

    def items(self):
        return self.obj.items()

    def set(self, *argv, **kwarg):
        self.obj.set(*argv, **kwarg)
        return self

    def remove(self):
        self.obj.remove()
        return self

    def __enter__(self):
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.commit()

    def __repr__(self):
        return repr(self.obj)

    def __getitem__(self, key):
        return self.obj[key]

    def __setitem__(self, key, value):
        self.obj[key] = value



class Sync_DB(Sync_Base):

    def export(self, f='stdout'):
        return self._main_sync_call(self.obj.schema.export)

    def backup(self, spec):
        return self._main_sync_call(self.obj.schema.backup, spec)


class Sync_View(Sync_Base):

    def _get_sync_class(self):
        return {'interfaces': SyncInterface}.get(self.obj.table, Sync_Object)

    def __getitem__(self, key, table=None):
        item = self._main_sync_call(self.obj.__getitem__, key, table)
        return self._get_sync_class()(self.event_loop, item)

    def __contains__(self, key):
        return key in self.keys()

    def getmany(self, spec, table=None):
        for item in tuple(self._main_sync_generator(self.obj.getmany, spec, table)):
            yield item

    def getone(self, spec, table=None):
        return self._main_sync_call(self.obj.getone, spec, table)

    def keys(self):
        for record in self.dump():
            yield record

    def create(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.create, *argspec, **kwarg)
        return self._get_sync_class()(self.event_loop, item)

    def ensure(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.ensure, *argspec, **kwarg)
        return self._get_sync_class()(self.event_loop, item)

    def add(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.add, *argspec, **kwarg)
        return self._get_sync_class()(self.event_loop, item)

    def wait(self, **spec):
        item = self._main_async_call(self.obj.wait, **spec)
        return self._get_sync_class()(self.event_loop, item)

    def exists(self, key, table=None):
        return self._main_sync_call(self.obj.exists, key, table)

    def locate(self, spec=None, table=None, **kwarg):
        item = self._main_sync_call(self.obj.locate, spec, table, **kwarg)
        return self._get_sync_class()(self.event_loop, item)

    def summary(self):
        return RecordSet(self._main_sync_generator(self.obj.summary))

    def dump(self):
        return RecordSet(self._main_sync_generator(self.obj.dump))


class Sync_Source(Sync_Object):

    def api(self, name, *argv, **kwarg):
        ret = self._main_sync_call(self.obj.api, name, *argv, **kwarg)
        return ret


class Sync_Sources(Sync_View):

    def __getitem__(self, key):
        item = self._main_sync_call(self.obj.__getitem__, key)
        return Sync_Source(self.event_loop, item)

    def add(self, **spec):
        item = self._main_async_call(self.obj.add, **spec)
        return self._get_sync_class()(self.event_loop, item)

    def remove(self, target, code=errno.ECONNRESET, sync=True):
        item = self._main_sync_call(self.obj.remove, target, code, sync)
        return self._get_sync_class()(self.event_loop, item)

    def keys(self):
        for record in self.obj.keys():
            yield record


class SyncInterface(Sync_Object):

    def __init__(self, event_loop, obj):
        super().__init__(event_loop, obj)
        self.ipaddr = Sync_View(event_loop, obj.ipaddr)

    @property
    def state(self):
        return self.obj.state

    def add_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.obj.add_ip, spec, **kwarg)
        return self

    def del_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.obj.del_ip, spec, **kwarg)
        return self

    def ensure_ip(self, spec=None, **kwarg):
        self._main_sync_call(self.obj.ensure_ip, spec, **kwarg)
        return self

    def load_from_system(self):
        self._main_async_call(self.obj.load_from_system)

