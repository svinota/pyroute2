'''
Simple routes
=============

Ordinary routes management is really simple::

    (ndb            # create a route
     .routes
     .create(dst='10.0.0.0/24', gateway='192.168.122.1')
     .commit())

    (ndb            # retrieve a route and change it
     .routes['10.0.0.0/24']
     .set('gateway', '192.168.122.10')
     .set('priority', 500)
     .commit())

    (ndb            # remove a route
     .routes['10.0.0.0/24']
     .remove()
     .commit())


Multiple routing tables
=======================

But Linux systems have more than one routing table::

    >>> set((x.table for x in ndb.routes.summary()))
    {101, 254, 255, 5001, 5002}

The main routing table is 254. All the routes people mostly work with are
in that table. To address routes in other routing tables, you can use dict
specs::

    (ndb
     .routes
     .create(dst='10.0.0.0/24', gateway='192.168.122.1', table=101)
     .commit())

    (ndb
     .routes[{'table': 101, 'dst': '10.0.0.0/24'}]
     .set('gateway', '192.168.122.10')
     .set('priority', 500)
     .commit())

    (ndb
     .routes[{'table': 101, 'dst': '10.0.0.0/24'}]
     .remove()
     .commit())

Route metrics
=============

`route['metrics']` attribute provides a dictionary-like object that
reflects route metrics like hop limit, mtu etc::

    # set up all metrics from a dictionary
    (ndb
     .routes['10.0.0.0/24']
     .set('metrics', {'mtu': 1500, 'hoplimit': 20})
     .commit())

    # fix individual metrics
    (ndb
     .routes['10.0.0.0/24']['metrics']
     .set('mtu', 1500)
     .set('hoplimit', 20)
     .commit())

'''

from pyroute2.ndb.objects import RTNL_Object
from pyroute2.ndb.report import Record
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh

_dump_rt = ['rt.f_%s' % x[0] for x in rtmsg.sql_schema()][:-2]
_dump_nh = ['nh.f_%s' % x[0] for x in nh.sql_schema()][:-2]


class Route(RTNL_Object):

    table = 'routes'
    msg_class = rtmsg
    hidden_fields = ['route_id']
    api = 'route'
    summary = '''
              SELECT
                  rt.f_target, rt.f_tflags, rt.f_RTA_TABLE, rt.f_RTA_DST,
                  rt.f_dst_len, rt.f_RTA_GATEWAY, nh.f_RTA_GATEWAY
              FROM
                  routes AS rt
              LEFT JOIN nh
              ON
                  rt.f_route_id = nh.f_route_id
                  AND rt.f_target = nh.f_target
              '''
    table_alias = 'rt'
    summary_header = ('target', 'tflags', 'table', 'dst',
                      'dst_len', 'gateway', 'nexthop')
    dump = '''
           SELECT rt.f_target,rt.f_tflags,%s
           FROM routes AS rt
           LEFT JOIN nh AS nh
           ON rt.f_route_id = nh.f_route_id
               AND rt.f_target = nh.f_target
           ''' % ','.join(['%s' % x for x in _dump_rt + _dump_nh])
    dump_header = (['target', 'tflags'] +
                   [rtmsg.nla2name(x[5:]) for x in _dump_rt] +
                   ['nh_%s' % nh.nla2name(x[5:]) for x in _dump_nh])

    _replace_on_key_change = True

    def mark_tflags(self, mark):
        plch = (self.schema.plch, ) * 4
        self.schema.execute('''
                            UPDATE interfaces SET
                                f_tflags = %s
                            WHERE
                                (f_index = %s OR f_index = %s)
                                AND f_target = %s
                            ''' % plch,
                            (mark,
                             self['iif'],
                             self['oif'],
                             self['target']))

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = rtmsg
        self.event_map = {rtmsg: "load_rtnlmsg"}
        dict.__setitem__(self, 'multipath', [])
        dict.__setitem__(self, 'metrics', {})
        super(Route, self).__init__(*argv, **kwarg)

    def complete_key(self, key):
        ret_key = {}
        if isinstance(key, basestring):
            ret_key['dst'] = key
        elif isinstance(key, (Record, tuple, list)):
            return super(Route, self).complete_key(key)
        elif isinstance(key, dict):
            ret_key.update(key)
        else:
            raise TypeError('unsupported key type')

        if 'target' not in ret_key:
            ret_key['target'] = 'localhost'

        table = ret_key.get('table', ret_key.get('RTA_TABLE', 254))
        if 'table' not in ret_key:
            ret_key['table'] = table

        if isinstance(ret_key.get('dst_len'), basestring):
            ret_key['dst_len'] = int(ret_key['dst_len'])

        if isinstance(ret_key.get('dst'), basestring):
            if ret_key.get('dst') == 'default':
                ret_key['dst'] = ''
                ret_key['dst_len'] = 0
            elif '/' in ret_key['dst']:
                ret_key['dst'], ret_key['dst_len'] = ret_key['dst'].split('/')

        return super(Route, self).complete_key(ret_key)

    @property
    def clean(self):
        clean = True
        for s in (self['metrics'], ) + tuple(self['multipath']):
            if hasattr(s, 'changed'):
                clean &= len(s.changed) == 0
        return clean & super(Route, self).clean

    def make_req(self, prime):
        req = dict(prime)
        for key in self.changed:
            req[key] = self[key]
        if self['multipath']:
            req['multipath'] = self['multipath']
        if self['metrics']:
            req['metrics'] = self['metrics']
        if self.get('gateway'):
            req['gateway'] = self['gateway']
        return req

    def __setitem__(self, key, value):
        if key in ('dst', 'src') and '/' in value:
            net, net_len = value.split('/')
            if net in ('0', '0.0.0.0'):
                net = ''
            super(Route, self).__setitem__(key, net)
            super(Route, self).__setitem__('%s_len' % key, int(net_len))
        elif key == 'dst' and value == 'default':
            super(Route, self).__setitem__('dst', '')
            super(Route, self).__setitem__('dst_len', 0)
        elif key == 'route_id':
            raise ValueError('route_id is read only')
        elif key == 'multipath':
            super(Route, self).__setitem__('multipath', [])
            for mp in value:
                mp = dict(mp)
                if self.state == 'invalid':
                    mp['create'] = True
                obj = NextHop(self, self.view, mp)
                obj.state.set(self.state.get())
                self['multipath'].append(obj)
            if key in self.changed:
                self.changed.remove(key)
        elif key == 'metrics':
            value = dict(value)
            if self.state == 'invalid':
                value['create'] = True
            obj = Metrics(self, self.view, value)
            obj.state.set(self.state.get())
            super(Route, self).__setitem__('metrics', obj)
            if key in self.changed:
                self.changed.remove(key)
        else:
            super(Route, self).__setitem__(key, value)

    def apply(self, rollback=False):
        if (self.get('table') == 255) and \
                (self.get('family') == 10) and \
                (self.get('proto') == 2):
            # skip automatic ipv6 routes with proto kernel
            return self
        else:
            return super(Route, self).apply(rollback)

    def load_sql(self, *argv, **kwarg):
        super(Route, self).load_sql(*argv, **kwarg)
        if not self.load_event.is_set():
            return
        if 'nh_id' not in self and self.get('route_id') is not None:
            nhs = (self
                   .schema
                   .fetch('SELECT * FROM nh WHERE f_route_id = %s' %
                          (self.schema.plch, ), (self['route_id'], )))
            metrics = (self
                       .schema
                       .fetch('SELECT * FROM metrics WHERE f_route_id = %s' %
                              (self.schema.plch, ), (self['route_id'], )))

            if len(tuple(metrics)):
                self['metrics'] = Metrics(self, self.view,
                                          {'route_id': self['route_id']})
            flush = False
            idx = 0
            for nexthop in tuple(self['multipath']):
                if not isinstance(nexthop, NextHop):
                    flush = True

                if not flush:
                    try:
                        spec = next(nhs)
                    except StopIteration:
                        flush = True
                    for key, value in zip(nexthop.names, spec):
                        if key in nexthop and value is None:
                            continue
                        else:
                            nexthop.load_value(key, value)
                if flush:
                    self['multipath'].pop(idx)
                    continue
                idx += 1

            for nexthop in nhs:
                key = {'route_id': self['route_id'],
                       'nh_id': nexthop[-1]}
                self['multipath'].append(NextHop(self, self.view, key))


class RouteSub(object):

    def apply(self, *argv, **kwarg):
        return self.route.apply(*argv, **kwarg)

    def commit(self, *argv, **kwarg):
        return self.route.commit(*argv, **kwarg)


class NextHop(RouteSub, RTNL_Object):

    msg_class = nh
    table = 'nh'
    hidden_fields = ('route_id', 'target')

    def mark_tflags(self, mark):
        plch = (self.schema.plch, ) * 4
        self.schema.execute('''
                            UPDATE interfaces SET
                                f_tflags = %s
                            WHERE
                                (f_index = %s OR f_index = %s)
                                AND f_target = %s
                            ''' % plch,
                            (mark,
                             self.route['iif'],
                             self.route['oif'],
                             self.route['target']))

    def __init__(self, route, *argv, **kwarg):
        self.route = route
        kwarg['iclass'] = nh
        super(NextHop, self).__init__(*argv, **kwarg)


class Metrics(RouteSub, RTNL_Object):

    msg_class = rtmsg.metrics
    table = 'metrics'
    hidden_fields = ('route_id', 'target')

    def mark_tflags(self, mark):
        plch = (self.schema.plch, ) * 4
        self.schema.execute('''
                            UPDATE interfaces SET
                                f_tflags = %s
                            WHERE
                                (f_index = %s OR f_index = %s)
                                AND f_target = %s
                            ''' % plch,
                            (mark,
                             self.route['iif'],
                             self.route['oif'],
                             self.route['target']))

    def __init__(self, route, *argv, **kwarg):
        self.route = route
        kwarg['iclass'] = rtmsg.metrics
        super(Metrics, self).__init__(*argv, **kwarg)
