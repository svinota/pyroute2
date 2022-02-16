from pr2modules.netlink import nlmsg


class errmsg(nlmsg):
    '''
    Custom message type

    Error ersatz-message
    '''

    fields = (('code', 'i'),)
