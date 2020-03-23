import json
from itertools import chain
from pyroute2.common import basestring

MAX_REPORT_LINES = 10000


def format_json(dump, headless=False):

    buf = []
    fnames = None
    yield '['
    for record in dump:
        if fnames is None:
            if headless:
                fnames = record._names
            else:
                fnames = record
                continue
        if buf:
            buf[-1] += ','
            for line in buf:
                yield line
            buf = []
        lines = json.dumps(dict(zip(fnames, record)), indent=4).split('\n')
        buf.append('    {')
        for line in sorted(lines[1:-1]):
            if line[-1] == ',':
                line = line[:-1]
            buf.append('    %s,' % line)
        buf[-1] = buf[-1][:-1]
        buf.append('    }')
    for line in buf:
        yield line
    yield ']'


def format_csv(dump, headless=False):

    def dump_record(rec):
        row = []
        for field in rec:
            if isinstance(field, int):
                row.append('%i' % field)
            elif field is None:
                row.append('')
            else:
                row.append("'%s'" % field)
        return row

    fnames = None
    for record in dump:
        if fnames is None and headless:
            fnames = True
            yield ','.join(dump_record(record._names))
        yield ','.join(dump_record(record))


class Record(object):

    def __init__(self, names, values):
        if len(names) != len(values):
            raise ValueError('names and values must have the same length')
        self._names = tuple(names)
        self._values = tuple(values)

    def __getitem__(self, key):
        idx = len(self._names)
        for i in reversed(self._names):
            idx -= 1
            if i == key:
                return self._values[idx]

    def __setitem__(self, *argv, **kwarg):
        raise TypeError('immutable object')

    def __getattribute__(self, key):
        if key.startswith('_'):
            return object.__getattribute__(self, key)
        else:
            return self[key]

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise TypeError('immutable object')
        return object.__setattr__(self, key, value)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        return repr(self._values)

    def __len__(self):
        return len(self._values)

    def _as_dict(self):
        ret = {}
        for key, value in zip(self._names, self._values):
            ret[key] = value
        return ret

    def __eq__(self, right):
        n = all(x[0] == x[1] for x in zip(self._names, right._names))
        v = all(x[0] == x[1] for x in zip(self._values, right._values))
        return n and v


class BaseReport(object):

    def __init__(self, generator, ellipsis=True):
        self.generator = generator
        self.ellipsis = ellipsis
        self.cached = []

    def __iter__(self):
        return self.generator

    def __repr__(self):
        counter = 0
        ret = []
        for record in self.generator:
            if isinstance(record, basestring):
                ret.append(record)
            else:
                ret.append(repr(record))
            ret.append('\n')
            counter += 1
            if self.ellipsis and counter > MAX_REPORT_LINES:
                ret.append('(...)')
                break
        if ret:
            ret.pop()
        return ''.join(ret)


class Report(BaseReport):

    def transform(self, **kwarg):

        def g():
            for record in self.generator:
                if isinstance(record, Record):
                    values = []
                    names = record._names
                    for name, value in zip(names, record._values):
                        if name in kwarg:
                            value = kwarg[name](value)
                        values.append(value)
                    record = Record(names, values)
                yield record

        return Report(g())

    def filter(self, f=None, **kwarg):

        def g():
            for record in self.generator:
                m = True
                for key in kwarg:
                    if kwarg[key] != getattr(record, key):
                        m = False
                if m:
                    if f is None:
                        yield record
                    elif f(record):
                        yield record

        return Report(g())

    def select(self, *argv):

        def g():
            for record in self.generator:
                ret = []
                for field in argv:
                    ret.append(getattr(record, field, None))
                yield Record(argv, ret)

        return Report(g())

    def join(self, right, condition=lambda r1, r2: True, prefix=''):
        # fetch all the records from the right
        # ACHTUNG it may consume a lot of memory
        right = tuple(right)

        def g():

            for r1 in self.generator:
                for r2 in right:
                    if condition(r1, r2):
                        n = tuple(chain(r1._names, ['%s%s' % (prefix, x)
                                                    for x in r2._names]))
                        v = tuple(chain(r1._values, r2._values))
                        yield Record(n, v)

        return Report(g())

    def format(self, kind):
        if kind == 'json':
            return BaseReport(format_json(self.generator, headless=True))
        elif kind == 'csv':
            return BaseReport(format_csv(self.generator, headless=True))
        else:
            raise ValueError()

    def __getitem__(self, key):
        if isinstance(key, int):
            if key >= 0:
                # positive indices
                for x in range(key):
                    try:
                        next(self.generator)
                    except StopIteration:
                        raise IndexError('index out of range')
                try:
                    return next(self.generator)
                except StopIteration:
                    raise IndexError('index out of range')
            else:
                # negative indices
                buf = []
                for i in self.generator:
                    buf.append(i)
                    if len(buf) > abs(key):
                        buf.pop(0)
                if len(buf) < abs(key):
                    raise IndexError('index out of range')
                return buf[0]
        elif isinstance(key, slice):
            count = 0
            buf = []
            start = key.start or 0
            stop = key.stop

            for i in self.generator:
                buf.append(i)
                if (start >= 0 and count < start) or \
                        (start < 0 and len(buf) > abs(start)):
                    buf.pop(0)
                count += 1
                if stop is not None and stop > 0 and count == stop:
                    if start < 0:
                        buf.pop(0)
                    break

            if stop is not None and stop < 0:
                buf = buf[:stop]

            return buf[::key.step]
        else:
            raise TypeError('illegal key format')
