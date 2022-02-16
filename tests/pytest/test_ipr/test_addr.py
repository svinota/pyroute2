import time
import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.context_manager import skip_if_not_supported


test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_add(context):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr('add', index=index, address=ipaddr, prefixlen=24)
    ndb.addresses.wait(index=index, address=ipaddr, timeout=5)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_replace(context):
    index, ifname = context.default_interface
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr('add', index=index, address=ipaddr1, prefixlen=24)
    ndb.addresses.wait(index=index, address=ipaddr1, timeout=5)
    ipr.addr('replace', index=index, address=ipaddr2, prefixlen=24)
    ndb.addresses.wait(index=index, address=ipaddr2, timeout=5)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_add_local(context):
    index, ifname = context.default_interface
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr('add', index=index, address=ipaddr1, local=ipaddr2, prefixlen=24)
    ndb.addresses.wait(index=index, address=ipaddr1, local=ipaddr2, timeout=5)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_add_broadcast(context):
    index, ifname = context.default_interface
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr(
        'add', index=index, address=ipaddr1, broadcast=ipaddr2, prefixlen=24
    )
    ndb.addresses.wait(
        index=index, address=ipaddr1, broadcast=ipaddr2, timeout=5
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_add_broadcast_default(context):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr('add', index=index, address=ipaddr, broadcast=True, prefixlen=24)
    interface = ndb.addresses.wait(index=index, address=ipaddr, timeout=5)
    assert interface['broadcast'] is not None


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_filter(context):
    index, ifname = context.default_interface
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    ipaddrB = context.new_ipaddr
    ipr = context.ipr
    ndb = context.ndb

    ipr.addr(
        'add', index=index, address=ipaddr1, broadcast=ipaddrB, prefixlen=24
    )
    ipr.addr(
        'add', index=index, address=ipaddr2, broadcast=ipaddrB, prefixlen=24
    )
    ndb.addresses.wait(index=index, address=ipaddr1, timeout=5)
    ndb.addresses.wait(index=index, address=ipaddr2, timeout=5)
    assert len(ipr.get_addr(index=index)) == 2
    assert len(ipr.get_addr(address=ipaddr1)) == 1
    assert len(ipr.get_addr(broadcast=ipaddrB)) == 2
    assert len(ipr.get_addr(match=lambda x: x['index'] == index)) == 2


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_addr_flush(context):
    index, ifname = context.default_interface
    addresses = [
        context.new_ipaddr,
        context.new_ipaddr,
        context.new_ipaddr,
        context.new_ipaddr,
    ]
    ipr = context.ipr
    ndb = context.ndb
    counter = 5

    for ipaddr in addresses:
        ipr.addr('add', index=index, address=ipaddr, prefixlen=24)
    for ipaddr in addresses:
        ndb.addresses.wait(index=index, address=ipaddr, timeout=5)
    ipr.flush_addr(index=index)
    while counter:
        for ipaddr in tuple(addresses):
            if ipaddr not in ndb.addresses:
                addresses.remove(ipaddr)
        if not addresses:
            break
        time.sleep(1)
        counter -= 1
    else:
        raise Exception()
