from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh

_dump_rt = ['rt.f_%s' % x[0] for x in rtmsg.sql_schema()][:-2]
_dump_nh = ['nh.f_%s' % x[0] for x in nh.sql_schema()][:-2]


class Route(RTNL_Object):

    table = 'routes'
    msg_class = rtmsg
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
        super(Route, self).__init__(*argv, **kwarg)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['RTA_DST'], ret_key['dst_len'] = key.split('/')

        return super(Route, self).complete_key(ret_key)

    def make_req(self, prime):
        req = dict(prime)
        for key in self.changed:
            req[key] = self[key]
        if self['multipath']:
            req['multipath'] = self['multipath']
        return req

    def load_sql(self, *argv, **kwarg):
        super(Route, self).load_sql(*argv, **kwarg)
        if not self.load_event.is_set():
            return
        if 'nh_id' not in self and self.get('route_id') is not None:
            nhs = (self
                   .schema
                   .fetch('SELECT * FROM nh WHERE f_route_id = %s' %
                          (self.schema.plch, ), (self['route_id'], )))
            flush = False
            for nexthop in tuple(self['multipath']):
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
                    self['multipath'].pop()
                    continue
            for nexthop in nhs:
                key = {'route_id': self['route_id'],
                       'nh_id': nexthop[-1]}
                self['multipath'].append(NextHop(self.view, key))


class NextHop(Route):

    msg_class = nh
    table = 'nh'
    reverse_update = {'table': 'nh',
                      'name': 'nh_f_tflags',
                      'field': 'f_tflags',
                      'sql': '''
                          UPDATE routes
                          SET f_tflags = NEW.f_tflags
                          WHERE f_route_id = NEW.f_route_id;
                      '''}
