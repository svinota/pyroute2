from pr2modules.netlink import rtnl
from pr2modules.netlink import NETLINK_ROUTE
from pr2modules.netlink.nlsocket import NetlinkSocket
from pr2modules.netlink.rtnl.marshal import MarshalRtnl


class RawIPRSocketMixin(object):
    def __init__(self, fileno=None):
        super(RawIPRSocketMixin, self).__init__(NETLINK_ROUTE, fileno=fileno)
        self.marshal = MarshalRtnl()

    def bind(self, groups=rtnl.RTMGRP_DEFAULTS, **kwarg):
        super(RawIPRSocketMixin, self).bind(groups, **kwarg)


class RawIPRSocket(RawIPRSocketMixin, NetlinkSocket):
    pass
