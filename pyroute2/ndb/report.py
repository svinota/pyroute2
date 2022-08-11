'''
.. note:: New in verision 0.5.11

Filtering examples::

    # 1. get all the routes
    # 2. join with interfaces on route.oif == interface.index
    # 3. select only fields dst, gateway, ifname and mac address
    # 4. transform the mac address into xxxx.xxxx.xxxx notation
    # 5. dump the info in the CSV format

    (ndb
     .routes
     .dump()
     .join(ndb.interfaces.dump(),
           condition=lambda l, r: l.oif == r.index)
     .select('dst', 'gateway', 'oif', 'ifname', 'address')
     .transform(address=lambda x: '%s%s.%s%s.%s%s' % tuple(x.split(':')))
     .format('csv'))

    'dst','gateway','oif','ifname','address'
    '172.16.20.0','127.0.0.2',1,'lo','0000.0000.0000'
    '172.16.22.0','127.0.0.4',1,'lo','0000.0000.0000'
    '','172.16.254.3',3,'wlp58s0','60f2.6289.400e'
    '10.250.3.0',,39,'lxcbr0','0016.3e00.0000'
    '10.255.145.0','10.255.152.254',42881,'prdc51e6d5','4a6a.60b1.8448'
    ...


'''
import json
import warnings
from itertools import chain

from pyroute2 import cli

MAX_REPORT_LINES = 10000

deprecation_notice = '''
RecordSet API is deprecated, pls refer to:
'''


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


class Record:
    def __init__(self, names, values, ref_class=None):
        self._names = tuple(names)
        self._values = tuple(values)
        if len(self._names) != len(self._values):
            raise ValueError('names and values must have the same length')
        self._ref_class = ref_class

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

    def _select_fields(self, *fields):
        return Record(fields, map(lambda x: self[x], fields), self._ref_class)

    def _match(self, f=None, **spec):
        if callable(f):
            return f(self)
        for key, value in spec.items():
            if not (
                value(self[key]) if callable(value) else (self[key] == value)
            ):
                return False
        return True

    def _as_dict(self):
        ret = {}
        for key, value in zip(self._names, self._values):
            ret[key] = value
        return ret

    def __eq__(self, right):
        if hasattr(right, '_names'):
            n = all(x[0] == x[1] for x in zip(self._names, right._names))
            v = all(x[0] == x[1] for x in zip(self._values, right._values))
            return n and v
        elif isinstance(right, dict):
            for key, value in right.items():
                if value != self[key]:
                    break
            else:
                return True
            return False
        elif self._ref_class is not None and isinstance(right, (str, int)):
            return self._ref_class.compare_record(self, right)
        else:
            return all(x[0] == x[1] for x in zip(self._values, right))


class BaseRecordSet(object):
    def __init__(self, generator, ellipsis='(...)'):
        self.generator = generator
        self.ellipsis = ellipsis

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.generator)

    def __repr__(self):
        counter = 0
        ret = []
        for record in self.generator:
            if isinstance(record, str):
                ret.append(record)
            else:
                ret.append(repr(record))
            ret.append('\n')
            counter += 1
            if self.ellipsis and counter > MAX_REPORT_LINES:
                ret.append(self.ellipsis)
                break
        if ret:
            ret.pop()
        return ''.join(ret)


class RecordSet(BaseRecordSet):
    '''
    NDB views return objects of this class with `summary()` and `dump()`
    methods. RecordSet objects are generator-based, they do not store the
    data in the memory, but transform them on the fly.

    RecordSet filters also return objects of this class, thus making possible
    to make chains of filters.
    '''

    def __init__(self, generator, ellipsis=True):
        super().__init__(generator, ellipsis)
        self.filters = []

    def __next__(self):
        while True:
            record = next(self.generator)
            for f in self.filters:
                record = f(record)
                if record is None:
                    break
            else:
                return record

    def select_fields(self, *fields):
        self.filters.append(lambda x: x._select_fields(*fields))

    def select_records(self, f=None, **spec):
        self.filters.append(lambda x: x if x._match(f, **spec) else None)

    @cli.show_result
    def transform(self, **kwarg):
        '''
        Transform record fields with a provided functions::

            view.transform(field_name_1=func1,
                           field_name_2=func2)

        Examples, transform MAC addresses into dots-format and IEEE 802::

            fmt = '%s%s.%s%s.%s%s'
            (ndb
             .interfaces
             .summary()
             .transform(address=lambda x: fmt % tuple(x.split(':')))

            (ndb
             .interfaces
             .summary()
             .transform(address=lambda x: x.replace(':', '-').upper()))
        '''

        def g():
            for record in self.generator:
                if isinstance(record, Record):
                    values = []
                    names = record._names
                    for name, value in zip(names, record._values):
                        if name in kwarg:
                            value = kwarg[name](value)
                        values.append(value)
                    record = Record(names, values, record._ref_class)
                yield record

        return RecordSet(g())

    @cli.show_result
    def filter(self, f=None, **kwarg):
        '''
        Filter records. This function may be called in two ways. One way
        is a simple match. Select ports of `br0` only in the `up` state::

            (ndb
             .interfaces
             .dump()
             .filter(master=ndb.interfaces['br0']['index'],
                     state='up'))

        When a simple match is not a solution, one can provide a matching
        function. Select only MPLS lwtunnel routes::

            (ndb
             .routes
             .dump()
             .filter(lambda x: x.encap_type == 1 and x.encap is not None))
        '''

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

        return RecordSet(g())

    @cli.show_result
    def select(self, *argv):
        warnings.warn(deprecation_notice, DeprecationWarning)
        return self.fields(*argv)

    @cli.show_result
    def fields(self, *fields):
        '''
        Show selected fields from records::

            ndb.interfaces.dump().fields('index', 'ifname', 'state')
        '''
        warnings.warn(deprecation_notice, DeprecationWarning)

        def g():
            for record in self.generator:
                yield record._select_fields(*fields)

        return RecordSet(g())

    @cli.show_result
    def join(self, right, condition=lambda r1, r2: True, prefix=''):
        '''
        Join two reports.

            * right -- a report to join with
            * condition -- filter records with a function
            * prefix -- rename the "right" fields using the prefix

        The condition function must have two arguments, left record and
        right record, and must return True or False. The routine discards
        joined records when the condition is False.

        Example, provide interface names for routes, don't change field
        names::

            (ndb
             .routes
             .dump()
             .join(ndb.interfaces.dump(),
                   condition=lambda l, r: l.oif == r.index)
             .select('dst', 'gateway', 'ifname'))

        **Warning**: this method loads the whole data of the `right` report
        into the memory.

        '''
        warnings.warn(deprecation_notice, DeprecationWarning)
        # fetch all the records from the right
        # ACHTUNG it may consume a lot of memory
        right = tuple(right)

        def g():

            for r1 in self.generator:
                for r2 in right:
                    if condition(r1, r2):
                        n = tuple(
                            chain(
                                r1._names,
                                ['%s%s' % (prefix, x) for x in r2._names],
                            )
                        )
                        v = tuple(chain(r1._values, r2._values))
                        yield Record(n, v, r1._ref_class)

        return RecordSet(g())

    @cli.show_result
    def format(self, kind):
        '''
        Return an iterator over text lines in the chosen format.

        Supported formats: 'json', 'csv'.
        '''
        if kind == 'json':
            return BaseRecordSet(format_json(self, headless=True))
        elif kind == 'csv':
            return BaseRecordSet(format_csv(self, headless=True))
        else:
            raise ValueError()

    def count(self):
        '''
        Return number of records.

        The method exhausts the generator.
        '''
        counter = 0
        for record in self:
            counter += 1
        return counter

    def __getitem__(self, key):
        return list(self)[key]
