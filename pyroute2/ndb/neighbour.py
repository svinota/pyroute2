from pyroute2.ndb.rtnl_object import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ndmsg import ndmsg


class Neighbour(RTNL_Object):

    table = 'neighbours'
    api = 'neigh'
    summary = '''
              SELECT
                  n.f_target, n.f_tflags,
                  i.f_IFLA_IFNAME, n.f_NDA_LLADDR, n.f_NDA_DST
              FROM
                  neighbours AS n
              INNER JOIN
                  interfaces AS i
              ON
                  n.f_ifindex = i.f_index
                  AND n.f_target = i.f_target
              '''
    summary_header = ('target', 'flags', 'ifname', 'lladdr', 'neighbour')

    def __init__(self, view, key, ctxid=None):
        self.event_map = {ndmsg: "load_rtnlmsg"}
        super(Neighbour, self).__init__(view, key, ndmsg, ctxid)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['NDA_DST'] = key

        return super(Neighbour, self).complete_key(ret_key)
