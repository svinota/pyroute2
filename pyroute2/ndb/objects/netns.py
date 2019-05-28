
from pyroute2.ndb.objects import RTNL_Object
from pyroute2.netlink.rtnl.nsinfmsg import nsinfmsg


class NetNS(RTNL_Object):

    table = 'netns'
    msg_class = nsinfmsg
    table_alias = 'n'

    def __init__(self, *argv, **kwarg):
        kwarg['iclass'] = nsinfmsg
        self.event_map = {nsinfmsg: "load_rtnlmsg"}
        super(NetNS, self).__init__(*argv, **kwarg)
