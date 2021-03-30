import pytest
from pr2test.tools import interface_exists
from pr2test.tools import address_exists
from pr2test.context_manager import make_test_matrix


test_matrix = make_test_matrix(targets=['local', 'netns'],
                               dbs=['sqlite3/:memory:', 'postgres/pr2test'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_multiple_interfaces(context):

    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    (context.ndb.begin()
     .push(context.ndb.interfaces
           .create(ifname=ifname1, kind='dummy')
           .set(state='up')
           .set(address='00:11:22:aa:aa:aa')
           .add_ip(address=ipaddr1, prefixlen=24),
           context.ndb.interfaces
           .create(ifname=ifname2, kind='dummy')
           .set(state='up')
           .set(address='00:11:22:bb:bb:bb')
           .add_ip(address=ipaddr2, prefixlen=24))
     .commit())

    assert interface_exists(context.netns,
                            ifname=ifname1,
                            address='00:11:22:aa:aa:aa')
    assert interface_exists(context.netns,
                            ifname=ifname2,
                            address='00:11:22:bb:bb:bb')
    assert address_exists(context.netns, ifname=ifname1, address=ipaddr1)
    assert address_exists(context.netns, ifname=ifname2, address=ipaddr2)
