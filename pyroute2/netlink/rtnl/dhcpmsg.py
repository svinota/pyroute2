from pyroute2.netlink import nla
from pyroute2.netlink import nlmsg


class dhcpmsg(nlmsg):
    '''
    Custom message type

    Option for a DHCP agent
    '''
    prefix = 'DHCP_'

    fields = (('family', 'H'),
              ('prefixlen', 'H'),
              ('index', 'I'))

    nla_map = (('DHCP_UNSPEC', 'none'),
               ('DHCP_ADDRESS', 'ipaddr'),
               ('DHCP_IFNAME', 'asciiz'),
               ('DHCP_AGENTINFO', 'agentinfo'))

    class agentinfo(nla):
        nla_map = (('DHCP_AGENT', 'asciiz'),
                   ('DHCP_AGENT_PID', 'uint32'),
                   ('DHCP_AGENT_STATUS', 'asciiz'))
