import threading
from socket import AF_UNSPEC
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.req import IPRouteRequest
from pyroute2.ipdb.transactional import Transactional


class Route(Transactional):

    def __init__(self, ipdb, mode=None):
        Transactional.__init__(self, ipdb, mode)
        self._exists = False
        self._load_event = threading.Event()
        self._fields = [rtmsg.nla2name(i[0]) for i in rtmsg.nla_map]
        self._fields.append('flags')
        self._fields.append('src_len')
        self._fields.append('dst_len')
        self._fields.append('table')
        self._fields.append('removal')
        self.cleanup = ('attrs',
                        'header',
                        'event')

    def load_netlink(self, msg):
        with self._direct_state:
            self._exists = True
            self.update(msg)
            # merge key
            for (name, value) in msg['attrs']:
                norm = rtmsg.nla2name(name)
                self[norm] = value
                # normalize RTAX
                if norm == 'metrics':
                    ret = {}
                    for (rtax, rtax_value) in value['attrs']:
                        rtax_norm = rtmsg.metrics.nla2name(rtax)
                        ret[rtax_norm] = rtax_value
                    self[norm] = ret

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
        self._load_event.wait()
        return self

    def commit(self, tid=None, transaction=None, rollback=False):
        self._load_event.clear()
        error = None

        if tid:
            transaction = self._transactions[tid]
        else:
            transaction = transaction or self.last()

        # create a new route
        if not self._exists:
            try:
                self.nl.route('add', **IPRouteRequest(self))
            except Exception:
                self.nl = None
                self.ipdb.routes.remove(self)
                raise

        # work on existing route
        snapshot = self.pick()
        try:
            # route set
            request = IPRouteRequest(transaction - snapshot)
            if any([request[x] is not None for x in request]):
                self.nl.route('set', **IPRouteRequest(transaction))

            if transaction.get('removal'):
                self.nl.route('delete', **IPRouteRequest(snapshot))

        except Exception as e:
            if not rollback:
                ret = self.commit(transaction=snapshot, rollback=True)
                if isinstance(ret, Exception):
                    error = ret
                else:
                    error = e
            else:
                self.drop()
                x = RuntimeError()
                x.cause = e
                raise x

        if not rollback:
            self.drop()
            self.reload()

        if error is not None:
            error.transaction = transaction
            raise error

        return self

    def remove(self):
        self['removal'] = True
        return self


class RoutingTables(dict):

    def __init__(self, ipdb):
        dict.__init__(self)
        self.ipdb = ipdb
        self.tables = {254: {}}

    def add(self, spec=None, **kwarg):
        '''
        Create a route from a dictionary
        '''
        spec = spec or kwarg
        table = spec.get('table', 254)
        assert 'dst' in spec
        route = Route(self.ipdb)
        route.update(spec)
        if table not in self.tables:
            self.tables[table] = dict()
        self.tables[table][route['dst']] = route
        route.begin()
        return route

    def load_netlink(self, msg):
        '''
        Loads an existing route from a rtmsg
        '''
        table = msg.get('table', 254)
        if table not in self.tables:
            self.tables[table] = dict()

        dst = msg.get_attr('RTA_DST', None)
        if dst is None:
            key = 'default'
        else:
            key = '%s/%s' % (dst, msg.get('dst_len', 0))

        if key in self.tables[table]:
            ret = self.tables[table][key]
            ret.load_netlink(msg)
        else:
            ret = Route(ipdb=self.ipdb)
            ret.load_netlink(msg)
            self.tables[table][key] = ret
        return ret

    def remove(self, route, table=None):
        if isinstance(route, Route):
            table = route.get('table', 254)
            route = route.get('dst', 'default')
        else:
            table = table or 254
        del self.tables[table][route]

    def get(self, dst, table=None):
        table = table or 254
        return self.tables[table][dst]

    def keys(self, table=254, family=AF_UNSPEC):
        return [x['dst'] for x in self.tables[table].values()
                if (x['family'] == family) or (family == AF_UNSPEC)]

    def has_key(self, key, table=254):
        return key in self.tables[table]

    def __contains__(self, key):
        return key in self.tables[254]

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        assert key == value['dst']
        return self.add(value)

    def __delitem__(self, key):
        return self.remove(key)
