import pytest
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


@pytest.mark.parametrize('smode', ('IPVLAN_MODE_L2', 'IPVLAN_MODE_L3'))
def test_create_ipvlan(context, smode):
    master = context.new_ifname
    ipvlan = context.new_ifname
    # create the master link
    index = context.ndb.interfaces.create(
        ifname=master, kind='dummy'
    ).commit()['index']
    # check modes
    # maybe move modes dict somewhere else?
    cmode = ifinfmsg.ifinfo.data_map['ipvlan'].modes[smode]
    assert ifinfmsg.ifinfo.data_map['ipvlan'].modes[cmode] == smode
    # create ipvlan
    context.ipr.link(
        'add', ifname=ipvlan, kind='ipvlan', link=index, mode=cmode
    )
    interface = context.ndb.interfaces.wait(ifname=ipvlan, timeout=5)
    assert interface['link'] == index
    assert interface['ipvlan_mode'] == cmode
