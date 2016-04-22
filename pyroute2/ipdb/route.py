import types
import logging
import threading
from collections import namedtuple
from socket import AF_UNSPEC
from pyroute2.common import basestring
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh as rtmsg_nh
from pyroute2.netlink.rtnl.req import IPRouteRequest
from pyroute2.ipdb.transactional import Transactional
from pyroute2.ipdb.linkedset import LinkedSet


class Metrics(Transactional):

    _fields = [rtmsg.metrics.nla2name(i[0]) for i in rtmsg.metrics.nla_map]


class Encap(Transactional):
    _fields = ['type', 'labels']


class NextHopSet(LinkedSet):

    def __init__(self, prime=None):
        super(NextHopSet, self).__init__()
        prime = prime or []
        for v in prime:
            self.add(v)

    def __sub__(self, vs):
        ret = type(self)()
        sub = set(self.raw.keys()) - set(vs.raw.keys())
        for v in sub:
            ret.add(self[v], raw=self.raw[v])
        return ret

    def __make_nh(self, prime):
        return (prime.get('flags', 0),
                prime.get('hops', 0),
                prime.get('ifindex', 0),
                prime.get('gateway'))

    def __getitem__(self, key):
        return dict(zip(('flags', 'hops', 'ifindex', 'gateway'), key))

    def __iter__(self):
        def NHIterator():
            for x in tuple(self.raw.keys()):
                yield self[x]
        return NHIterator()

    def add(self, prime, raw=None):
        return super(NextHopSet, self).add(self.__make_nh(prime))

    def remove(self, prime, raw=None):
        hit = False
        for nh in self:
            for key in prime:
                if prime[key] != nh.get(key):
                    break
            else:
                hit = True
                super(NextHopSet, self).remove(self.__make_nh(nh))
        if not hit:
            raise KeyError('nexthop not found')


class WatchdogKey(dict):
    '''
    Construct from a route a dictionary that could be used as
    a match for IPDB watchdogs.
    '''
    def __init__(self, route):
        dict.__init__(self, [x for x in IPRouteRequest(route).items()
                             if x[0] in ('dst', 'dst_len', 'oif',
                                         'iif', 'table')])


RouteKey = namedtuple('RouteKey',
                      ('src',
                       'dst',
                       'gateway',
                       'table',
                       'iif',
                       'oif'))
RouteKey._required = 3  # number of required fields (should go first)


def make_route_key(msg):
    '''
    Construct from a netlink message a key that can be used
    to locate the route in the table
    '''
    values = []
    if isinstance(msg, nlmsg):
        for field in RouteKey._fields:
            v = msg.get_attr(msg.name2nla(field))
            if field in ('src', 'dst'):
                if v is not None:
                    v = '%s/%s' % (v, msg['%s_len' % field])
                elif field == 'dst':
                    v = 'default'
            if v is None:
                v = msg.get(field, None)
            values.append(v)
    elif isinstance(msg, Transactional):
        for field in RouteKey._fields:
            v = msg.get(field, None)
            values.append(v)
    else:
        raise TypeError('prime not supported')
    return RouteKey(*values)


class Route(Transactional):
    '''
    Persistent transactional route object
    '''

    _fields = [rtmsg.nla2name(i[0]) for i in rtmsg.nla_map]
    for key, _ in rtmsg.fields:
        _fields.append(key)
    _fields.append('removal')
    _virtual_fields = ['ipdb_scope', 'ipdb_priority']
    _fields.extend(_virtual_fields)
    _linked_sets = ['multipath', ]
    _nested = ['encap', 'metrics']
    cleanup = ('attrs',
               'header',
               'event',
               'cacheinfo')

    def __init__(self, ipdb, mode=None, parent=None, uid=None):
        Transactional.__init__(self, ipdb, mode, parent, uid)
        self._load_event = threading.Event()
        with self._direct_state:
            self['multipath'] = NextHopSet()
            self['ipdb_priority'] = 0

    def add_nh(self, prime):
        with self._write_lock:
            tx = self.get_tx()
            with tx._direct_state:
                tx['multipath'].add(prime)

    def del_nh(self, prime):
        with self._write_lock:
            tx = self.get_tx()
            with tx._direct_state:
                tx['multipath'].remove(prime)

    def load_netlink(self, msg):
        with self._direct_state:
            if self['ipdb_scope'] == 'locked':
                # do not touch locked interfaces
                return

            self['ipdb_scope'] = 'system'
            self.update(msg)

            # merge key
            for (name, value) in msg['attrs']:
                norm = rtmsg.nla2name(name)
                # normalize RTAX
                if norm == 'metrics':
                    with self['metrics']._direct_state:
                        for metric in tuple(self['metrics'].keys()):
                            del self['metrics'][metric]
                        for (rtax, rtax_value) in value['attrs']:
                            rtax_norm = rtmsg.metrics.nla2name(rtax)
                            self['metrics'][rtax_norm] = rtax_value
                elif norm == 'multipath':
                    self['multipath'] = NextHopSet()
                    for v in value:
                        nh = {}
                        for name in [x[0] for x in rtmsg_nh.fields]:
                            nh[name] = v[name]
                        for (rta, rta_value) in v.get('attrs', ()):
                            rta_norm = rtmsg.nla2name(rta)
                            nh[rta_norm] = rta_value
                        self['multipath'].add(nh)
                elif norm == 'encap':
                    with self['encap']._direct_state:
                        ret = []
                        for l in value.get_attr('MPLS_IPTUNNEL_DST'):
                            ret.append(str(l['label']))
                        self['encap']['labels'] = '/'.join(ret)
                else:
                    self[norm] = value

            if msg.get_attr('RTA_DST', None) is not None:
                dst = '%s/%s' % (msg.get_attr('RTA_DST'),
                                 msg['dst_len'])
            else:
                dst = 'default'
            self['dst'] = dst

            if self['encap_type'] is not None:
                with self['encap']._direct_state:
                    self['encap']['type'] = self['encap_type']
                self['encap_type'] = None

            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]

            self.sync()

    def __setitem__(self, key, value):
        ret = value
        if (key in ('encap', 'metrics')) and isinstance(value, dict):
            # transactionals attach as is
            if type(value) in (Encap, Metrics):
                with self._direct_state:
                    return Transactional.__setitem__(self, key, value)

            # check, if it exists already
            ret = Transactional.__getitem__(self, key)
            # it doesn't
            # (plain dict can be safely discarded)
            if isinstance(ret, dict) or not ret:
                # bake transactionals in place
                if key == 'encap':
                    ret = Encap(parent=self)
                elif key == 'metrics':
                    ret = Metrics(parent=self)
                # attach transactional to the route
                with self._direct_state:
                    Transactional.__setitem__(self, key, ret)
                # begin() works only if the transactional is attached
                if any(value.values()):
                    if self._mode in ('implicit', 'explicit'):
                        ret._begin(tid=self.last().uid)
                    [ret.__setitem__(k, v) for k, v
                     in value.items() if v is not None]
            # corresponding transactional exists
            else:
                # set fields
                for k in ret:
                    ret[k] = value.get(k, None)
        else:
            Transactional.__setitem__(self, key, ret)

    def __getitem__(self, key):
        ret = Transactional.__getitem__(self, key)
        if (key in ('encap', 'metrics')) and (ret is None):
            with self._direct_state:
                self[key] = {}
                ret = self[key]
        return ret

    def sync(self):
        self._load_event.set()

    def reload(self):
        # do NOT call get_routes() here, it can cause race condition
        # self._load_event.wait()
        return self

    def commit(self, tid=None, transaction=None, rollback=False):
        self._load_event.clear()
        error = None
        drop = True

        if tid:
            transaction = self._transactions[tid]
        else:
            if transaction:
                drop = False
            else:
                transaction = self.last()

        # create a new route
        if self['ipdb_scope'] != 'system':
            try:
                self.ipdb.update_routes(self.nl.route('add', **transaction))
            except Exception:
                self.nl = None
                self.ipdb.routes.remove(self)
                raise

        # work on existing route
        snapshot = self.pick()
        diff = transaction - snapshot
        # if any of these three key arguments is changed,
        # create the cleanup key from snapshot
        #
        # the route reference with that key will be removed
        # from the table.idx index
        #
        # it is needed to cleanup obsoleted references to
        # routes with the key fields changed with 'set'
        # operation, when only the RTM_NEWROUTE message comes
        if ('gateway' in diff) or ('src' in diff) or ('dst' in diff):
            cleanup_key = {'gateway': snapshot['gateway'],
                           'src': snapshot['src'],
                           'dst': snapshot['dst']}
        else:
            cleanup_key = None

        try:
            # route set
            request = IPRouteRequest(diff)
            cleanup = [any(snapshot['metrics'].values()) and
                       not any(diff.get('metrics', {}).values()),
                       any(snapshot['encap'].values()) and
                       not any(diff.get('encap', {}).values())]
            if any([request[x] not in (None, {'attrs': []})
                    for x in request]) or any(cleanup):
                self.ipdb.update_routes(
                    self.nl.route('set', **transaction))

            # route removal
            if (transaction['ipdb_scope'] in ('shadow', 'remove')) or\
                    ((transaction['ipdb_scope'] == 'create') and rollback):
                if transaction['ipdb_scope'] == 'shadow':
                    self.set_item('ipdb_scope', 'locked')
                self.ipdb.update_routes(
                    self.nl.route('delete', **snapshot))
                if transaction['ipdb_scope'] == 'shadow':
                    self.set_item('ipdb_scope', 'shadow')

        except Exception as e:
            if not rollback:
                ret = self.commit(transaction=snapshot, rollback=True)
                if isinstance(ret, Exception):
                    error = ret
                else:
                    error = e
            else:
                if drop:
                    self.drop()
                x = RuntimeError()
                x.cause = e
                raise x

        if drop and not rollback:
            self.drop()

        if error is not None:
            error.transaction = transaction
            raise error

        if not rollback:
            with self._direct_state:
                self['multipath'] = transaction['multipath']
            self.reload()

        if cleanup_key:
            # On route updates there is no RTM_DELROUTE -- we have to
            # remove the route key manually. Save the key and use it
            # if no exceptions occur
            try:
                del self.ipdb.routes.tables[self['table']][cleanup_key]
            except Exception as e:
                logging.warning('lost route key: %s' % cleanup_key)

        return self

    def remove(self):
        self['ipdb_scope'] = 'remove'
        return self

    def shadow(self):
        self['ipdb_scope'] = 'shadow'
        return self


class RoutingTable(object):

    def __init__(self, ipdb, prime=None):
        self.ipdb = ipdb
        self.lock = threading.Lock()
        self.idx = {}
        self.kdx = {}

    def __nogc__(self):
        return self.filter(lambda x: x['route']['ipdb_scope'] != 'gc')

    def __repr__(self):
        return repr([x['route'] for x in self.__nogc__()])

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        for record in self.__nogc__():
            yield record['route']

    def gc(self):
        for route in self.filter({'ipdb_scope': 'gc'}):
            try:
                self.ipdb.nl.route('get', **route['route'])
                with route['route']._direct_state:
                    route['route']['ipdb_scope'] = 'system'
            except:
                del self.idx[route['key']]

    def keys(self, key='dst'):
        with self.lock:
            return [x['route'][key] for x in self.__nogc__()]

    def filter(self, target, oneshot=False):
        #
        if isinstance(target, types.FunctionType):
            return filter(target, [x for x in self.idx.values()])

        if isinstance(target, basestring):
            target = {'dst': target}

        if not isinstance(target, dict):
            raise TypeError('target type not supported')

        ret = []
        for record in self.idx.values():
            for key, value in target.items():
                if (key not in record['route']) or \
                        (value != record['route'][key]):
                    break
            else:
                ret.append(record)
                if oneshot:
                    return ret

        return ret

    def describe(self, target, forward=False):
        # match the route by index -- a bit meaningless,
        # but for compatibility
        if isinstance(target, int):
            keys = tuple(self.idx.keys())
            return self.idx[keys[target]]

        # match the route by key
        if isinstance(target, (tuple, list)):
            try:
                # full match
                return self.idx[RouteKey(*target)]
            except KeyError:
                # w/o iif and oif
                # when a route is just created, there can be no oif and
                # iif specified, if they weren't provided explicitly,
                # and in that case there will be the key w/o oif and
                # iif
                r = RouteKey._required
                l = RouteKey._fields
                return self.idx[RouteKey(*(target[:r] +
                                           (None, ) * (len(l) - r)))]

        # match the route by filter
        ret = self.filter(target, oneshot=True)
        if ret:
            return ret[0]

        if not forward:
            raise KeyError('record not found')

        # match the route by dict spec
        if not isinstance(target, dict):
            raise TypeError('lookups can be done only with dict targets')

        # split masks
        if target.get('dst', '').find('/') >= 0:
            dst = target['dst'].split('/')
            target['dst'] = dst[0]
            target['dst_len'] = int(dst[1])

        if target.get('src', '').find('/') >= 0:
            src = target['src'].split('/')
            target['src'] = src[0]
            target['src_len'] = int(src[1])

        # load and return the route, if exists
        route = Route(self.ipdb)
        ret = self.ipdb.nl.get_routes(**target)
        if not ret:
            raise KeyError('record not found')
        route.load_netlink(ret[0])
        return {'route': route,
                'key': None}

    def __delitem__(self, key):
        with self.lock:
            item = self.describe(key, forward=False)
            del self.idx[make_route_key(item['route'])]

    def __setitem__(self, key, value):
        with self.lock:
            try:
                record = self.describe(key, forward=False)
            except KeyError:
                record = {'route': Route(self.ipdb),
                          'key': None}

            if isinstance(value, nlmsg):
                record['route'].load_netlink(value)
            elif isinstance(value, Route):
                record['route'] = value
            elif isinstance(value, dict):
                with record['route']._direct_state:
                    record['route'].update(value)

            key = make_route_key(record['route'])
            if record['key'] is None:
                self.idx[key] = {'route': record['route'],
                                 'key': key}
            else:
                self.idx[key] = record
                if record['key'] != key:
                    del self.idx[record['key']]
                    record['key'] = key

    def __getitem__(self, key):
        with self.lock:
            return self.describe(key, forward=False)['route']

    def __contains__(self, key):
        try:
            with self.lock:
                self.describe(key, forward=False)
            return True
        except KeyError:
            return False


class RoutingTableSet(object):

    def __init__(self, ipdb, ignore_rtables=None):
        self.ipdb = ipdb
        self.ignore_rtables = ignore_rtables or []
        self.tables = {254: RoutingTable(self.ipdb)}

    def add(self, spec=None, **kwarg):
        '''
        Create a route from a dictionary
        '''
        spec = spec or kwarg
        table = spec.get('table', 254)
        if 'dst' not in spec:
            raise ValueError('dst not specified')
        if table not in self.tables:
            self.tables[table] = RoutingTable(self.ipdb)
        route = Route(self.ipdb)
        multipath = spec.pop('multipath', [])
        route.update(spec)
        route.set_item('ipdb_scope', 'create')
        self.tables[table][route['dst']] = route
        route.begin()
        for nested in route._nested:
            if nested in spec:
                route[nested] = spec[nested]
        for nh in multipath:
            route.add_nh(nh)
        return route

    def load_netlink(self, msg):
        '''
        Loads an existing route from a rtmsg
        '''
        table = msg.get('table', 254)
        if table == 252:
            table = msg.get_attr('RTA_TABLE')

        if table in self.ignore_rtables:
            return

        if not isinstance(msg, rtmsg):
            return

        # construct a key
        # FIXME: temporary solution
        # FIXME: can `Route()` be used as a key?
        key = make_route_key(msg)

        # RTM_DELROUTE
        if msg['event'] == 'RTM_DELROUTE':
            try:
                # locate the record
                record = self.tables[table][key]
                # delete the record
                if record['ipdb_scope'] not in ('locked', 'shadow'):
                    del self.tables[table][key]
                    record.set_item('ipdb_scope', 'detached')
                # sync ???
                record.sync()
            except Exception as e:
                logging.debug(e)
                logging.debug(msg)
            return

        # RTM_NEWROUTE
        if table not in self.tables:
            self.tables[table] = RoutingTable(self.ipdb)
        self.tables[table][key] = msg
        return self.tables[table][key]

    def gc(self):
        for table in self.tables.keys():
            self.tables[table].gc()

    def remove(self, route, table=None):
        if isinstance(route, Route):
            table = route.get('table', 254) or 254
            route = route.get('dst', 'default')
        else:
            table = table or 254
        self.tables[table][route].remove()

    def filter(self, target):
        ret = []
        for table in self.tables.values():
            if table is not None:
                ret.extend(table.filter(target))
        return ret

    def describe(self, spec, table=254):
        return self.tables[table].describe(spec)

    def get(self, dst, table=None):
        table = table or 254
        return self.tables[table][dst]

    def keys(self, table=254, family=AF_UNSPEC):
        return [x['dst'] for x in self.tables[table]
                if (x.get('family') == family) or
                (family == AF_UNSPEC)]

    def has_key(self, key, table=254):
        return key in self.tables[table]

    def __contains__(self, key):
        return key in self.tables[254]

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        if key != value['dst']:
            raise ValueError("dst doesn't match key")
        return self.add(value)

    def __delitem__(self, key):
        return self.remove(key)

    def __repr__(self):
        return repr(self.tables[254])
