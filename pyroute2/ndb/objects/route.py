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

    reverse_update = {'table': 'routes',
                      'name': 'routes_f_tflags',
                      'field': 'f_tflags',
                      'sql': '''
                          UPDATE interfaces
                          SET f_tflags = NEW.f_tflags
                          WHERE (f_index = NEW.f_RTA_OIF OR
                                 f_index = NEW.f_RTA_IIF) AND
                                 f_target = NEW.f_target;
                      '''}

    _replace_on_key_change = True

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

        if 'table' not in ret_key:
            ret_key['table'] = 254

        if isinstance(ret_key.get('dst_len'), basestring):
            ret_key['dst_len'] = int(ret_key['dst_len'])

        if isinstance(ret_key.get('dst'), basestring):
            if ret_key.get('dst') == 'default':
                ret_key['dst'] = ''
                ret_key['dst_len'] = 0
            elif '/' in ret_key['dst']:
                ret_key['dst'], ret_key['dst_len'] = ret_key['dst'].split('/')

        return super(Route, self).complete_key(ret_key)

    def make_req(self, prime):
        req = dict(prime)
        for key in self.changed:
            req[key] = self[key]
        if self['multipath']:
            req['multipath'] = self['multipath']
        if self['metrics']:
            req['metrics'] = self['metrics']
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
        else:
            super(Route, self).__setitem__(key, value)
            if key in ('multipath', 'metrics'):
                self.changed.remove(key)

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
                self['metrics'] = Metrics(self.view,
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
                self['multipath'].append(NextHop(self.view, key))


class NextHop(RTNL_Object):

    msg_class = nh
    table = 'nh'
    hidden_fields = ('route_id', 'target')
    reverse_update = {'table': 'nh',
                      'name': 'nh_f_tflags',
                      'field': 'f_tflags',
                      'sql': '''
                          UPDATE routes
                          SET f_tflags = NEW.f_tflags
                          WHERE f_route_id = NEW.f_route_id;
                      '''}

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = nh
        super(NextHop, self).__init__(*argv, **kwarg)


class Metrics(RTNL_Object):

    msg_class = rtmsg.metrics
    table = 'metrics'
    hidden_fields = ('route_id', 'target')

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = rtmsg.metrics
        super(Metrics, self).__init__(*argv, **kwarg)
