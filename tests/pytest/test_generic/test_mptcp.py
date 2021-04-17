from pyroute2 import MPTCP


def get_endpoints(mptcp):
    return dict((x.get_nested('MPTCP_PM_ATTR_ADDR',
                              'MPTCP_PM_ADDR_ATTR_ADDR4'),
                 x.get_nested('MPTCP_PM_ATTR_ADDR',
                              'MPTCP_PM_ADDR_ATTR_ID'))
                for x in mptcp.endpoint('show'))


def get_limits(mptcp):
    return [(x.get_attr('MPTCP_PM_ATTR_SUBFLOWS'),
             x.get_attr('MPTCP_PM_ATTR_RCV_ADD_ADDRS'))
            for x in mptcp.limits('show')][0]


def test_enpoint_add_addr4(context):
    with MPTCP() as mptcp:
        ipaddrs = [context.new_ipaddr for _ in range(3)]
        for ipaddr in ipaddrs:
            mptcp.endpoint('add', addr=ipaddr)
        mapping = get_endpoints(mptcp)
        assert set(mapping) >= set(ipaddrs)
        for ipaddr in ipaddrs:
            mptcp.endpoint('del', addr=ipaddr, id=mapping[ipaddr])
        assert not set(get_endpoints(mptcp)).intersection(set(ipaddrs))


def test_limits():
    with MPTCP() as mptcp:
        save_subflows, save_rcv_add = get_limits(mptcp)
        mptcp.limits('set', subflows=2, rcv_add_addrs=3)
        assert get_limits(mptcp) == (2, 3)
        mptcp.limits('set', subflows=save_subflows, rcv_add_addrs=save_rcv_add)
        assert get_limits(mptcp) == (save_subflows, save_rcv_add)
