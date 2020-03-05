from collections import OrderedDict
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ndmsg import ndmsg


def load_ndmsg(schema, target, event):
    #
    # ignore events with ifindex == 0
    #
    if event['ifindex'] == 0:
        return

    schema.load_netlink('neighbours', target, event)


init = {'specs': [['neighbours', OrderedDict(ndmsg.sql_schema())]],
        'classes': [['neighbours', ndmsg]],
        'indices': [['neighbours', ('ifindex',
                                    'NDA_LLADDR')]],
        'foreign_keys': [['neighbours', [{'fields': ('f_target',
                                                     'f_tflags',
                                                     'f_ifindex'),
                                          'parent_fields': ('f_target',
                                                            'f_tflags',
                                                            'f_index'),
                                          'parent': 'interfaces'}]]],
        'event_map': {ndmsg: [load_ndmsg]}}


class Neighbour(RTNL_Object):

    table = 'neighbours'
    msg_class = ndmsg
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
    table_alias = 'n'
    summary_header = ('target', 'flags', 'ifname', 'lladdr', 'neighbour')

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ndmsg
        self.event_map = {ndmsg: "load_rtnlmsg"}
        super(Neighbour, self).__init__(*argv, **kwarg)

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': 'localhost'}

        if isinstance(key, basestring):
            ret_key['NDA_DST'] = key

        return super(Neighbour, self).complete_key(ret_key)
