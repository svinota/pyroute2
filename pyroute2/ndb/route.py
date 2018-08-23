from pyroute2.ndb.rtnl_object import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.rtmsg import nh

_dump_rt = ['rs.f_%s' % x[0] for x in rtmsg.sql_schema()][:-2]
_dump_nh = ['nh.f_%s' % x[0] for x in nh.sql_schema()][:-2]


class Route(RTNL_Object):

    table = 'routes'
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
    summary_header = ('target', 'flags', 'table', 'dst',
                      'dst_len', 'gateway', 'nexthop')
    dump = '''
           SELECT rs.f_target,rs.f_tflags,%s
           FROM routes AS rs
           LEFT JOIN nh AS nh
           ON rs.f_route_id = nh.f_route_id
               AND rs.f_target = nh.f_target
           ''' % ','.join(['%s' % x for x in _dump_rt + _dump_nh])
    dump_header = (['target', 'tflags'] +
                   [rtmsg.nla2name(x[5:]) for x in _dump_rt] +
                   ['nh_%s' % nh.nla2name(x[5:]) for x in _dump_nh])

    def __init__(self, view, key, ctxid=None):
        self.event_map = {rtmsg: "load_rtnlmsg"}
        super(Route, self).__init__(view, key, rtmsg, ctxid)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['RTA_DST'], ret_key['dst_len'] = key.split('/')

        return super(Route, self).complete_key(ret_key)
