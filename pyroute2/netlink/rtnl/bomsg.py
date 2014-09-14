from pyroute2.netlink.generic import nla
from pyroute2.netlink.generic import nlmsg


class bomsg(nlmsg):
    '''
    Custom message type

    Set bond parameters
    '''
    prefix = 'IFBO_'

    fields = (('index', 'I'), )

    nla_map = (('IFBO_UNSPEC', 'none'),
               ('IFBO_IFNAME', 'asciiz'),
               ('IFBO_COMMANDS', 'commands'))

    class commands(nla):
        nla_map = (('IFBO_MODE', 'uint32'),
                   ('IFBO_RESEND_IGMP', 'uint32'),
                   ('IFBO_USE_CARRIER', 'uint32'),
                   ('IFBO_MIN_LINKS', 'uint32'),
                   ('IFBO_LP_INTERVAL', 'uint32'))
