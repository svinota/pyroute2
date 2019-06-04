from pyroute2 import netns
from pyroute2.common import basestring
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.netlink.rtnl.nsinfmsg import nsinfmsg


class NetNS(RTNL_Object):

    table = 'netns'
    msg_class = nsinfmsg
    table_alias = 'n'
    api = 'netns'

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = nsinfmsg
        self.event_map = {nsinfmsg: "load_rtnlmsg"}
        super(NetNS, self).__init__(*argv, **kwarg)

    @classmethod
    def adjust_spec(cls, spec):
        if isinstance(spec, dict):
            ret_spec = spec
        else:
            ret_spec = {'target': 'localhost/netns'}
        if isinstance(spec, basestring):
            ret_spec['path'] = spec
        ret_spec['path'] = netns._get_netnspath(ret_spec['path'])
        return ret_spec

    def __setitem__(self, key, value):
        if self.state == 'system':
            raise ValueError('attempt to change a readonly object')
        if key == 'path':
            value = netns._get_netnspath(value)
        return super(NetNS, self).__setitem__(key, value)
