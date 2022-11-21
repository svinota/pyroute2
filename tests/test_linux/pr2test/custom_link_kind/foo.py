from pyroute2.netlink import nla

register_kind = 'vlan'


class vlan(nla):
    prefix = 'IFLA_'

    nla_map = (
        ('IFLA_FOO_UNSPEC', 'none'),
        ('IFLA_FOO_ID', 'uint16'),
        ('IFLA_FOO_FLAGS', 'vlan_flags'),
        ('IFLA_FOO_EGRESS_QOS', 'qos'),
        ('IFLA_FOO_INGRESS_QOS', 'qos'),
        ('IFLA_FOO_PROTOCOL', 'be16'),
    )

    class vlan_flags(nla):
        fields = (('flags', 'I'), ('mask', 'I'))

    class qos(nla):
        nla_map = (
            ('IFLA_VLAN_QOS_UNSPEC', 'none'),
            ('IFLA_VLAN_QOS_MAPPING', 'qos_mapping'),
        )

        class qos_mapping(nla):
            fields = (('from', 'I'), ('to', 'I'))
