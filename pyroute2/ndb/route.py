from pyroute2.ndb.rtnl_object import RTNL_Object
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

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = rtmsg
        self.event_map = {rtmsg: "load_rtnlmsg"}
        super(Route, self).__init__(*argv, **kwarg)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['RTA_DST'], ret_key['dst_len'] = key.split('/')

        return super(Route, self).complete_key(ret_key)


class NextHop(Route):

    msg_class = nh
    reverse_update = {'table': 'nh',
                      'name': 'nh_f_tflags',
                      'field': 'f_tflags',
                      'sql': '''
                          UPDATE routes
                          SET f_tflags = NEW.f_tflags
                          WHERE f_route_id = NEW.f_route_id;
                      '''}
