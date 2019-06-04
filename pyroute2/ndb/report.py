from pyroute2.common import basestring

MAX_REPORT_LINES = 100


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


class Report(object):

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
