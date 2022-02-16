from pr2modules.netlink import nla


class team(nla):
    prefix = 'IFLA_'

    nla_map = (('IFLA_TEAM_UNSPEC', 'none'), ('IFLA_TEAM_CONFIG', 'asciiz'))
