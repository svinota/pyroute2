import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.context_manager import skip_if_not_supported


test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_add(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.link('add', ifname=ifname, kind='dummy')
    index = ndb.interfaces.wait(ifname=ifname, timeout=5)['index']
    ipr.addr('add', index=index, address=ipaddr, prefixlen=24)
    ndb.addresses.wait(index=index, address=ipaddr, timeout=5)
