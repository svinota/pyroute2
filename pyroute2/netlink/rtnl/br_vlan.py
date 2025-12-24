from pyroute2.netlink import nla, nlmsg


class br_vlan_base(nlmsg):
    __slots__ = ()

    prefix = 'BRIDGE_VLANDB_'

    fields = (('family', 'B'), ('__pad', '3x'), ('ifindex', 'i'))


class br_vlan_query(br_vlan_base):
    __slots__ = ()

    nla_map = (
        ('BRIDGE_VLANDB_DUMP_UNSPEC', 'none'),
        ('BRIDGE_VLANDB_DUMP_FLAGS', 'uint32'),
    )


class br_vlan_msg(br_vlan_base):
    __slots__ = ()

    nla_map = (
        ('BRIDGE_VLANDB_UNSPEC', 'none'),
        ('BRIDGE_VLANDB_ENTRY', 'entry'),
        ('BRIDGE_VLANDB_GLOBAL_OPTIONS', 'gopts'),
    )

    class gopts(nla):
        prefix = 'BRIDGE_VLANDB_GOPTS_'
        nla_map = (
            ('BRIDGE_VLANDB_GOPTS_UNSPEC', 'none'),
            ('BRIDGE_VLANDB_GOPTS_ID', 'uint16'),
            ('BRIDGE_VLANDB_GOPTS_RANGE', 'uint16'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_SNOOPING', 'uint8'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_IGMP_VERSION', 'uint8'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_MLD_VERSION', 'uint8'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_LAST_MEMBER_CNT', 'uint32'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_STARTUP_QUERY_CNT', 'uint32'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_LAST_MEMBER_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_PAD', 'hex'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_MEMBERSHIP_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_QUERIER_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_QUERY_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_QUERY_RESPONSE_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_STARTUP_QUERY_INTVL', 'uint64'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_QUERIER', 'uint8'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_ROUTER_PORTS', 'hex'),
            ('BRIDGE_VLANDB_GOPTS_MCAST_QUERIER_STATE', 'hex'),
            ('BRIDGE_VLANDB_GOPTS_MSTI', 'uint16'),
        )

    class entry(nla):
        prefix = 'BRIDGE_VLANDB_ENTRY_'
        nla_map = (
            ('BRIDGE_VLANDB_ENTRY_UNSPEC', 'none'),
            ('BRIDGE_VLANDB_ENTRY_INFO', 'info'),
            ('BRIDGE_VLANDB_ENTRY_RANGE', 'uint16'),
            ('BRIDGE_VLANDB_ENTRY_STATE', 'uint8'),
            ('BRIDGE_VLANDB_ENTRY_TUNNEL_INFO', 'tinfo'),
            ('BRIDGE_VLANDB_ENTRY_STATS', 'stats'),
            ('BRIDGE_VLANDB_ENTRY_MCAST_ROUTER', 'uint8'),
            ('BRIDGE_VLANDB_ENTRY_MCAST_N_GROUPS', 'uint32'),
            ('BRIDGE_VLANDB_ENTRY_MCAST_MAX_GROUPS', 'uint32'),
            ('BRIDGE_VLANDB_ENTRY_NEIGH_SUPPRESS', 'uint8'),
        )

        class info(nla):
            fields = (('flags', 'H'), ('vid', 'H'))

        class tinfo(nla):
            prefix = 'BRIDGE_VLANDB_TINFO_'
            nla_map = (
                ('BRIDGE_VLANDB_TINFO_UNSPEC', 'none'),
                ('BRIDGE_VLANDB_TINFO_ID', 'uint32'),
                ('BRIDGE_VLANDB_TINFO_CMD', 'uint32'),
            )

        class stats(nla):
            prefix = 'BRIDGE_VLANDB_STATS_'
            nla_map = (
                ('BRIDGE_VLANDB_STATS_UNSPEC', 'none'),
                ('BRIDGE_VLANDB_STATS_RX_BYTES', 'uint64'),
                ('BRIDGE_VLANDB_STATS_RX_PACKETS', 'uint64'),
                ('BRIDGE_VLANDB_STATS_TX_BYTES', 'uint64'),
                ('BRIDGE_VLANDB_STATS_TX_PACKETS', 'uint64'),
                ('BRIDGE_VLANDB_STATS_PAD', 'hex'),
            )
