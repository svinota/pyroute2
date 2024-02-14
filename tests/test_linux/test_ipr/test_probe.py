import errno
from socket import AF_INET

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

    context.ipr.addr('add', index=index, address=ipaddr, prefixlen=24)
    context.ipr.link('set', index=index, state='up')
    context.ipr.link(
        'set', index=context.ipr.link_lookup(ifname='lo'), state='up'
    )

    context.ndb.interfaces.wait(ifname=ifname, state='up')
    context.ndb.interfaces.wait(ifname='lo', state='up')

    probes = [x for x in context.ipr.probe('add', kind='ping', dst=ipaddr)]
    probe = probes[0]

    assert len(probes) == 1
    assert probe['family'] == AF_INET
    assert probe['proto'] == 1
    assert probe['port'] == 0
    assert probe['dst_len'] == 32
    assert probe.get('dst') == ipaddr
    assert probe.get('kind') == 'ping'


@pytest.mark.parametrize(
    'context', make_test_matrix(targets=['netns']), indirect=True
)
@skip_if_not_supported
def test_ping_fail_ehostunreach(context):
    context.ipr.link(
        'set', index=context.ipr.link_lookup(ifname='lo'), state='down'
    )
    with pytest.raises(NetlinkError) as e:
        context.ipr.probe('add', kind='ping', dst='127.0.0.1')
    assert e.value.code == errno.EHOSTUNREACH


@pytest.mark.parametrize(
    'context', make_test_matrix(targets=['netns']), indirect=True
)
@skip_if_not_supported
def test_ping_fail_etimedout(context):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    target = context.new_ipaddr

    context.ipr.addr('add', index=index, address=ipaddr, prefixlen=24)
    context.ipr.link('set', index=index, state='up')
    context.ipr.link(
        'set', index=context.ipr.link_lookup(ifname='lo'), state='up'
    )

    context.ndb.interfaces.wait(ifname=ifname, state='up')
    context.ndb.interfaces.wait(ifname='lo', state='up')

    context.ipr.link(
        'set', index=context.ipr.link_lookup(ifname='lo'), state='up'
    )
    with pytest.raises(NetlinkError) as e:
        context.ipr.probe('add', kind='ping', dst=target)
    assert e.value.code == errno.ETIMEDOUT
