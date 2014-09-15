from pyroute2.netlink.generic import nla
from pyroute2.netlink.generic import nlmsg


class brmsg(nlmsg):
    '''
    Custom message type

    Set bridge parameters (STP, ageing, priority, etc)
    '''
    prefix = 'IFBR_'

    fields = (('index', 'I'), )

    nla_map = (('IFBR_UNSPEC', 'none'),
               ('IFBR_ADDRESS', 'l2addr'),
               ('IFBR_PORTINFO', 'portinfo'),
               ('IFBR_IFNAME', 'asciiz'),
               ('IFBR_COMMANDS', 'commands'))

    class portinfo(nla):
        fields = (('index', 'I'),
                  ('prio', 'B'),
                  ('hairpin', 'B'),
                  ('cost', 'H'))

        nla_map = (('IFBRPI_IFNAME', 'asciiz'))

    class commands(nla):
        nla_map = (('IFBR_STP_STATE', 'uint32'),
                   ('IFBR_MAX_AGE', 'uint32'))
