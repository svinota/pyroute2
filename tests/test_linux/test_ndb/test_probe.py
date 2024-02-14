import errno

import pytest
from pr2test.context_manager import make_test_matrix, skip_if_not_supported
from pr2test.marks import require_root

from pyroute2 import NetlinkError

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_ping_ok(context):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr

    with context.ndb.interfaces[ifname] as i:
        i.add_ip(address=ipaddr, prefixlen=24)
        i.set(state='up')

    with context.ndb.interfaces['lo'] as i:
        i.set(state='up')

    context.ndb.probes.create(kind='ping', dst=ipaddr).commit()


@pytest.mark.parametrize(
    'context', make_test_matrix(targets=['netns']), indirect=True
)
@skip_if_not_supported
def test_ping_fail_ehostunreach(context):
    with context.ndb.interfaces['lo'] as i:
        i.set(state='down')
    with pytest.raises(NetlinkError) as e:
        context.ndb.probes.create(kind='ping', dst='127.0.0.1').commit()
    assert e.value.code == errno.EHOSTUNREACH


@pytest.mark.parametrize(
    'context', make_test_matrix(targets=['netns']), indirect=True
)
@skip_if_not_supported
def test_ping_fail_etimedout(context):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    target = context.new_ipaddr

    with context.ndb.interfaces[ifname] as i:
        i.add_ip(address=ipaddr, prefixlen=24)
        i.set(state='up')
    with context.ndb.interfaces['lo'] as i:
        i.set(state='up')
    with pytest.raises(NetlinkError) as e:
        context.ndb.probes.create(kind='ping', dst=target).commit()
    assert e.value.code == errno.ETIMEDOUT
