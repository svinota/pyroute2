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


RouteKey = namedtuple('RouteKey', ('src', 'dst', 'gw', 'iif', 'oif'))


def make_route_key(msg):
    '''
    Construct from a netlink message a key that can be used
    to locate the route in the table
    '''
    if isinstance(msg, nlmsg):
        src = None
        # calculate dst
        if msg.get_attr('RTA_DST', None) is not None:
            dst = '%s/%s' % (msg.get_attr('RTA_DST'),
                             msg['dst_len'])
        else:
            dst = 'default'
        # use output | input interfaces as key also
        iif = msg.get_attr(msg.name2nla('iif'))
        oif = msg.get_attr(msg.name2nla('oif'))
        gw = msg.get_attr(msg.name2nla('gateway'))
    elif isinstance(msg, Transactional):
        src = None
        dst = msg.get('dst')
        iif = msg.get('iif')
        oif = msg.get('oif')
        gw = msg.get('gateway')
    else:
        raise TypeError('prime not supported')
    return RouteKey(src=src, dst=dst, gw=gw, iif=iif, oif=oif)


class Route(Transactional):
    '''
    Persistent transactional route object
    '''

    _fields = [rtmsg.nla2name(i[0]) for i in rtmsg.nla_map]
    _fields.append('flags')
    _fields.append('src_len')
    _fields.append('dst_len')
    _fields.append('table')
    _fields.append('removal')
    _virtual_fields = ['ipdb_scope', 'ipdb_priority']
    _fields.extend(_virtual_fields)
    _linked_sets = ['multipath', ]
    cleanup = ('attrs',
               'header',
               'event',
               'cacheinfo')

    def __init__(self, ipdb, mode=None, parent=None, uid=None):
        Transactional.__init__(self, ipdb, mode, parent, uid)
        self._load_event = threading.Event()
        with self._direct_state:
            for i in self._fields:
                self[i] = None
            self['metrics'] = Metrics(parent=self)
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

            # re-init metrics
            metrics = self.get('metrics', Metrics(parent=self))
            with metrics._direct_state:
                for metric in tuple(metrics.keys()):
                    del metrics[metric]
            self['metrics'] = metrics

            # merge key
            for (name, value) in msg['attrs']:
                norm = rtmsg.nla2name(name)
                # normalize RTAX
                if norm == 'metrics':
                    with self['metrics']._direct_state:
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
                else:
                    self[norm] = value

            if msg.get_attr('RTA_DST', None) is not None:
                dst = '%s/%s' % (msg.get_attr('RTA_DST'),
                                 msg['dst_len'])
            else:
                dst = 'default'
            self['dst'] = dst
            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]

            self.sync()

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
                self.ipdb.update_routes(
                    self.nl.route('add', **IPRouteRequest(transaction)))
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
        if diff['gateway'] or diff['src'] or diff['dst']:
            cleanup_key = {'gateway': snapshot['gateway'],
                           'src': snapshot['src'],
                           'dst': snapshot['dst']}
        else:
            cleanup_key = None

        try:
            # route set
            request = IPRouteRequest(diff)
            if any([request[x] not in (None, {'attrs': []}) for x in request]):
                self.ipdb.update_routes(
                    self.nl.route('set', **IPRouteRequest(transaction)))

            # route removal
            if (transaction['ipdb_scope'] in ('shadow', 'remove')) or\
                    ((transaction['ipdb_scope'] == 'create') and rollback):
                if transaction['ipdb_scope'] == 'shadow':
                    self.set_item('ipdb_scope', 'locked')
                self.ipdb.update_routes(
                    self.nl.route('delete', **IPRouteRequest(snapshot)))
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

    def __repr__(self):
        return repr([x['route'] for x in self.idx.values()])

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        for record in tuple(self.idx.values()):
            yield record['route']

    def keys(self, key='dst'):
        with self.lock:
            return [x['route'][key] for x in self.idx.values()]

    def describe(self, target, forward=True):
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
                return self.idx[RouteKey(*(target[:3] + (None, None)))]

        # match the route by string
        if isinstance(target, basestring):
            target = {'dst': target}

        # match the route by dict spec
        if not isinstance(target, dict):
            raise TypeError('unsupported key type')
        for record in self.idx.values():
            for key in target:
                # skip non-existing keys
                #
                # it's a hack, but newly-created routes
                # don't contain all the fields that are
                # in the netlink message
                if key not in record['route']:
                    continue
                # if any key doesn't match
                if target[key] != record['route'][key]:
                    break
            else:
                # if all keys match
                return record

        if not forward:
            raise KeyError('record not found')

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
        metrics = spec.pop('metrics', {})
        multipath = spec.pop('multipath', [])
        route.update(spec)
        route.metrics.update(metrics)
        route.set_item('ipdb_scope', 'create')
        self.tables[table][route['dst']] = route
        route.begin()
        for nh in multipath:
            route.add_nh(nh)
        return route

    def load_netlink(self, msg):
        '''
        Loads an existing route from a rtmsg
        '''
        table = msg.get('table', 254)
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

    def remove(self, route, table=None):
        if isinstance(route, Route):
            table = route.get('table', 254) or 254
            route = route.get('dst', 'default')
        else:
            table = table or 254
        self.tables[table][route].remove()

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
