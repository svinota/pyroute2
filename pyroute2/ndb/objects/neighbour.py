from collections import OrderedDict
from pyroute2.config import AF_BRIDGE
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.ndb.events import RescheduleException
from pyroute2.common import basestring
from pyroute2.netlink.rtnl.ndmsg import ndmsg


def load_ndmsg(schema, target, event):
    #
    # ignore events with ifindex == 0
    #
    if event['ifindex'] == 0:
        return
    #
    # AF_BRIDGE events
    #
    if event['family'] == AF_BRIDGE:
        #
        # bypass for now
        #
        try:
            schema.load_netlink('af_bridge_fdb', target, event, propagate=True)
        except Exception:
            raise RescheduleException()

    else:
        schema.load_netlink('neighbours', target, event)


init = {'specs': [['neighbours', OrderedDict(ndmsg.sql_schema())],
                  ['af_bridge_fdb', OrderedDict(ndmsg.sql_schema())]],
        'classes': [['neighbours', ndmsg],
                    ['af_bridge_fdb', ndmsg]],
        'indices': [['neighbours', ('ifindex', 'NDA_LLADDR', 'NDA_VLAN')],
                    ['af_bridge_fdb', ('ifindex', 'NDA_LLADDR', 'NDA_VLAN')]],
        'foreign_keys': [['neighbours', [{'fields': ('f_target',
                                                     'f_tflags',
                                                     'f_ifindex'),
                                          'parent_fields': ('f_target',
                                                            'f_tflags',
                                                            'f_index'),
                                          'parent': 'interfaces'}]],
                         ['af_bridge_fdb', [{'fields': ('f_target',
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

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            plch = view.ndb.schema.plch
            where = '''
                    WHERE
                        main.f_target = %s AND
                        main.f_ifindex = %s
                    ''' % (plch, plch)
            values = [view.chain['target'], view.chain['index']]
        else:
            where = ''
            values = []
        return (where, values)

    @classmethod
    def summary(cls, view):
        req = '''
              SELECT
                  main.f_target, main.f_tflags,
                  intf.f_IFLA_IFNAME, main.f_NDA_LLADDR, main.f_NDA_DST
              FROM
                  neighbours AS main
              INNER JOIN
                  interfaces AS intf
              ON
                  main.f_ifindex = intf.f_index
                  AND main.f_target = intf.f_target
              '''
        yield ('target', 'flags', 'ifname', 'lladdr', 'neighbour')
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

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

    def make_req(self, prime):
        req = super(Neighbour, self).make_req(prime)
        if 'vlan' in req and req['vlan'] == 0:
            req.pop('vlan')
        return req
