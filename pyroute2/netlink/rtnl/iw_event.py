from pyroute2.netlink.generic import nla


class iw_event(nla):

    nla_map = ((0x8B14, 'SIOCSIWAP', 'hex'),
               (0x8B15, 'SIOCGIWAP', 'hex'),
               (0x8B17, 'SIOCGIWAPLIST', 'hex'),
               (0x8B18, 'SIOCSIWSCAN', 'hex'),
               (0x8B19, 'SIOCGIWSCAN', 'hex'))
