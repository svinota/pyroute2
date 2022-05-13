import errno
import ipaddress

from pr2modules.common import basestring
from pr2modules.config import AF_BRIDGE
from pr2modules.netlink.rtnl.ndmsg import ndmsg

from ..events import RescheduleException
from ..objects import FieldFilter, RTNL_Object, ObjectData


def load_ndmsg(schema, target, event):
    #
    # ignore events with ifindex == 0
    #
    if event['ifindex'] == 0:
        return
    #
    if event.get_attr('NDA_IFINDEX') is None:
        event['attrs'].append(('NDA_IFINDEX', event['ifindex']))
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


ndmsg_schema = (
    ndmsg.sql_schema()
    .unique_index('ifindex', 'NDA_LLADDR', 'NDA_VLAN')
    .foreign_key(
        'interfaces',
        ('f_target', 'f_tflags', 'f_ifindex'),
        ('f_target', 'f_tflags', 'f_index'),
    )
)

brmsg_schema = (
    ndmsg.sql_schema()
    .unique_index('ifindex', 'NDA_LLADDR', 'NDA_VLAN')
    .foreign_key(
        'interfaces',
        ('f_target', 'f_tflags', 'f_ifindex'),
        ('f_target', 'f_tflags', 'f_index'),
    )
)

init = {
    'specs': [['neighbours', ndmsg_schema], ['af_bridge_fdb', brmsg_schema]],
    'classes': [['neighbours', ndmsg], ['af_bridge_fdb', ndmsg]],
    'event_map': {ndmsg: [load_ndmsg]},
}


def fallback_add(self, idx_req, req):
    (
        self.ndb._event_queue.put(
            self.sources[self['target']].api(self.api, 'dump'),
            source=self['target'],
        )
    )
    self.load_sql()


class NeighbourFieldFilter(FieldFilter):
    def index(self, context, value):
        return {'ifindex': value}

    def dst(self, context, value):
        if isinstance(value, str) and ':' in value:
            return {'dst': ipaddress.ip_address(value).compressed}
        return {'dst': value}


class Neighbour(RTNL_Object):

    table = 'neighbours'
    msg_class = ndmsg
    field_filter = NeighbourFieldFilter
    api = 'neigh'

    @classmethod
    def _dump_where(cls, view):
        if view.chain:
            plch = view.ndb.schema.plch
            where = '''
                    WHERE
                        main.f_target = %s AND
                        main.f_ifindex = %s
                    ''' % (
                plch,
                plch,
            )
            values = [view.chain['target'], view.chain['index']]
        else:
            where = ''
            values = []
        return (where, values)

    @classmethod
    def summary(cls, view):
        req = f'''
              SELECT
                  main.f_target, main.f_tflags,
                  intf.f_IFLA_IFNAME, main.f_NDA_LLADDR, main.f_NDA_DST
              FROM
                  {cls.table} AS main
              INNER JOIN
                  interfaces AS intf
              ON
                  main.f_ifindex = intf.f_index
                  AND main.f_target = intf.f_target
              '''
        yield ('target', 'tflags', 'ifname', 'lladdr', 'dst')
        where, values = cls._dump_where(view)
        for record in view.ndb.schema.fetch(req + where, values):
            yield record

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = ndmsg
        self.event_map = {ndmsg: "load_rtnlmsg"}
        super(Neighbour, self).__init__(*argv, **kwarg)
        self.fallback_for['add'][errno.EEXIST] = fallback_add

    def complete_key(self, key):
        if isinstance(key, dict):
            ret_key = key
        else:
            ret_key = {'target': self.ndb.localhost}

        if isinstance(key, basestring):
            ret_key['NDA_DST'] = key

        return super(Neighbour, self).complete_key(ret_key)

    @classmethod
    def spec_normalize(cls, spec):
        return ObjectData(cls.field_filter(), context=spec, prime=spec)

    def make_req(self, prime):
        req = super(Neighbour, self).make_req(prime)
        if 'vlan' in req and req['vlan'] == 0:
            req.pop('vlan')
        return req


class FDBRecord(Neighbour):

    table = 'af_bridge_fdb'
    msg_class = ndmsg
    api = 'fdb'

    @classmethod
    def summary(cls, view):
        for record in super(FDBRecord, cls).summary(view):
            yield record[:-1]

    def make_idx_req(self, prime):
        req = super(FDBRecord, self).make_req(prime)
        if 'NDA_VLAN' in req and req['NDA_VLAN'] == 0:
            req.pop('NDA_VLAN')
        return req
