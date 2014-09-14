from pyroute2.netlink.generic import nla
from pyroute2.netlink.generic import nlmsg


class errmsg(nlmsg):
    '''
    Custom message type

    Error ersatz-message
    '''
    fields = (('code', 'i'), )
