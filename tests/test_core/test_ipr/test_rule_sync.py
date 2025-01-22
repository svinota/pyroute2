from socket import AF_INET, AF_INET6

import pytest
from pr2test.tools import rule_exists


@pytest.mark.parametrize(
    'priority,spec',
    [
        (30313, {'table': 10}),
        (30314, {'table': 10, 'src': None}),
        (30315, {'table': 10, 'dst': None}),
        (30316, {'table': 10, 'dst': '127.0.0.0/24'}),
        (30317, {'table': 10, 'src': '127.0.0.0/24'}),
    ],
)
@pytest.mark.parametrize(
    'sync_ipr',
    [{'netns': True, 'ext_ack': True, 'strict_check': True}],
    indirect=True,
)
def test_rule_strict_src(sync_ipr, priority, spec):
    netns = sync_ipr.status['netns']
    sync_ipr.rule('add', priority=priority, **spec)
    assert rule_exists(priority=priority, netns=netns)


@pytest.mark.parametrize(
    'priority,proto,spec',
    [
        (20100, AF_INET, {'table': 10}),
        (20101, AF_INET, {'table': 10, 'fwmark': 15}),
        (20102, AF_INET, {'table': 10, 'fwmark': 15, 'fwmask': 20}),
        (20103, AF_INET, {'table': 2048, 'FRA_FWMARK': 10, 'FRA_FWMASK': 12}),
        (20104, AF_INET, {'table': 2048, 'src': '127.0.1.0', 'src_len': 24}),
        (20105, AF_INET, {'table': 2048, 'dst': '127.0.1.0', 'dst_len': 24}),
        (20106, AF_INET6, {'table': 5192, 'src': 'fd00::', 'src_len': 8}),
        (20107, AF_INET6, {'table': 5192, 'dst': 'fd00::', 'dst_len': 8}),
    ],
)
@pytest.mark.parametrize('sync_ipr', [{'netns': True}], indirect=True)
def test_rule_add_del(sync_ipr, priority, proto, spec):
    netns = sync_ipr.status['netns']
    sync_ipr.rule('add', priority=priority, **spec)
    assert rule_exists(priority=priority, proto=proto, netns=netns)
    assert (
        len([x for x in sync_ipr.rule('dump', priority=priority, **spec)]) == 1
    )
    sync_ipr.rule('del', priority=priority, **spec)
    assert not rule_exists(
        priority=priority, proto=proto, netns=netns, timeout=0.1
    )
