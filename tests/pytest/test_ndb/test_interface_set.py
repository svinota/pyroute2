import pytest
from pr2test.tools import interface_exists
from pr2test.context_manager import make_test_matrix

tnl_matrix = make_test_matrix(targets=['local', 'netns'],
                              types=['gre', 'ipip', 'sit'],
                              dbs=['sqlite3/:memory:', 'postgres/pr2test'])


def _test_gre_endpoints(context, state):
    ifname = context.new_ifname
    ipaddr_local1 = context.new_ipaddr
    ipaddr_local2 = context.new_ipaddr
    ipaddr_remote = context.new_ipaddr

    (context
     .ndb
     .interfaces
     .create(ifname=ifname,
             state=state,
             kind='gre',
             gre_local=ipaddr_local1,
             gre_remote=ipaddr_remote,
             gre_ttl=254)
     .commit())

    def match(ifname, ipaddr):
        return lambda x: x.get_nested('IFLA_LINKINFO',
                                      'IFLA_INFO_KIND') == 'gre' and \
            x.get_attr('IFLA_IFNAME') == ifname and \
            x.get_nested('IFLA_LINKINFO',
                         'IFLA_INFO_DATA',
                         'IFLA_GRE_LOCAL') == ipaddr

    assert interface_exists(context.netns, match(ifname, ipaddr_local1))

    (context
     .ndb
     .interfaces[ifname]
     .set(gre_local=ipaddr_local2)
     .commit())

    assert interface_exists(context.netns, match(ifname, ipaddr_local2))


@pytest.mark.parametrize('context', tnl_matrix, indirect=True)
def test_gre_endpoints_down(context):
    return _test_gre_endpoints(context, 'down')


@pytest.mark.parametrize('context', tnl_matrix, indirect=True)
def test_gre_endpoints_up(context):
    return _test_gre_endpoints(context, 'up')
