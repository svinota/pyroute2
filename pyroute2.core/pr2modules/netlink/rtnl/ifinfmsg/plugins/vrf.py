from pr2modules.netlink import nla


class vrf(nla):
    prefix = 'IFLA_'
    nla_map = (('IFLA_VRF_UNSPEC', 'none'), ('IFLA_VRF_TABLE', 'uint32'))
