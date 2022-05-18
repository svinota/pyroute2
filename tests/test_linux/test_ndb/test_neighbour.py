import pytest
from pr2test.context_manager import make_test_matrix, skip_if_not_implemented
from pr2test.tools import neighbour_exists

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_neighbour_simple(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    neighbour = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )
    (
        context.ndb.neighbours.create(
            ifindex=context.ndb.interfaces[ifname]['index'],
            dst=neighbour,
            lladdr='00:11:22:33:44:55',
        ).commit()
    )

    assert neighbour_exists(
        context.netns,
        ifindex=context.ndb.interfaces[ifname]['index'],
        dst=neighbour,
        lladdr='00:11:22:33:44:55',
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_neighbour_chain(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    neighbour = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ipaddr, prefixlen=24)
        .commit()
        .chain.neighbours.create(dst=neighbour, lladdr='00:11:22:33:44:55')
        .commit()
    )

    assert neighbour_exists(
        context.netns,
        ifindex=context.ndb.interfaces[ifname]['index'],
        dst=neighbour,
        lladdr='00:11:22:33:44:55',
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_implemented
def test_add_neighbour_method(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    neighbour = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .add_neighbour(dst=neighbour, lladdr='00:11:22:33:44:55')
        .commit()
    )

    assert neighbour_exists(
        context.netns,
        ifindex=context.ndb.interfaces[ifname]['index'],
        dst=neighbour,
        lladdr='00:11:22:33:44:55',
    )
