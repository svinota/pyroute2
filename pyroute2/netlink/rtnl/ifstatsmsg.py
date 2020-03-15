from pyroute2.netlink import nlmsg


class ifstatsmsg(nlmsg):
    fields = (('family', 'B'),
              ('pad1', 'B'),
              ('pad2', 'H'),
              ('ifindex', 'I'),
              ('filter_mask', 'I'))

    nla_map = (('IFLA_STATS_UNSPEC', 'none'),
               ('IFLA_STATS_LINK_64', 'hex'),
               ('IFLA_STATS_LINK_XSTATS', 'hex'),
               ('IFLA_STATS_LINK_XSTATS_SLAVE', 'hex'),
               ('IFLA_STATS_LINK_OFFLOAD_XSTATS', 'hex'),
               ('IFLA_STATS_AF_SPEC', 'hex'))
