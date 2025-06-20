import asyncio
import errno
from queue import Queue

from .report import RecordSet


class SyncBase:

    def __init__(self, event_loop, obj, class_map=None):
        self.event_loop = event_loop
        self.obj = obj
        self.class_map = {} if class_map is None else class_map

    def _get_sync_class(self, item, key=None):
        if key is None:
            key = self.obj.table
        return self.class_map.get(key, self.class_map.get('default'))(
            self.event_loop, item, self.class_map
        )

    async def _tm_sync_generator(self, queue, func, *argv, **kwarg):
        for record in func(*argv, **kwarg):
            queue.put(record)
        queue.put(None)

    def _main_sync_generator(self, func, *argv, **kwarg):
        queue = Queue()
        task = asyncio.run_coroutine_threadsafe(
            self._tm_sync_generator(queue, func, *argv, **kwarg),
            self.event_loop,
        )
        while True:
            record = queue.get()
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


class SyncDB(SyncBase):

    def export(self, f='stdout'):
        return self._main_sync_call(self.obj.schema.export)

    def backup(self, spec):
        return self._main_sync_call(self.obj.schema.backup, spec)


class SyncView(SyncBase):

    def __getitem__(self, key, table=None):
        item = self._main_sync_call(self.obj.__getitem__, key, table)
        return self._get_sync_class(item)

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return self.keys()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get(self, spec=None, table=None, **kwarg):
        item = self._main_sync_call(self.obj.get, spec, table, **kwarg)
        if item is not None:
            return self._get_sync_class(item)

    def getmany(self, spec, table=None):
        for item in tuple(
            self._main_sync_generator(self.obj.getmany, spec, table)
        ):
            yield item

    def getone(self, spec, table=None):
        return self._main_sync_call(self.obj.getone, spec, table)

    def keys(self):
        for record in self.dump():
            yield record

    def create(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.create, *argspec, **kwarg)
        return self._get_sync_class(item)

    def ensure(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.ensure, *argspec, **kwarg)
        return self._get_sync_class(item)

    def add(self, *argspec, **kwarg):
        item = self._main_sync_call(self.obj.add, *argspec, **kwarg)
        return self._get_sync_class(item)

    def wait(self, **spec):
        item = self._main_async_call(self.obj.wait, **spec)
        return self._get_sync_class(item)

    def exists(self, key, table=None):
        return self._main_sync_call(self.obj.exists, key, table)

    def locate(self, spec=None, table=None, **kwarg):
        item = self._main_sync_call(self.obj.locate, spec, table, **kwarg)
        return self._get_sync_class(item)

    def summary(self):
        return RecordSet(self._main_sync_generator(self.obj.summary))

    def dump(self):
        return RecordSet(self._main_sync_generator(self.obj.dump))


class SyncSources(SyncView):

    def __getitem__(self, key):
        item = self._main_sync_call(self.obj.__getitem__, key)
        return self._get_sync_class(item)

    def add(self, **spec):
        item = self._main_async_call(self.obj.add, **spec)
        return self._get_sync_class(item)

    def remove(self, target, code=errno.ECONNRESET, sync=True):
        item = self._main_sync_call(self.obj.remove, target, code, sync)
        return self._get_sync_class(item)

    def keys(self):
        for record in self.obj.keys():
            yield record
