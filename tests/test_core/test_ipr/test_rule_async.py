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
    'async_ipr',
    [{'netns': True, 'ext_ack': True, 'strict_check': True}],
    indirect=True,
)
@pytest.mark.asyncio
async def test_rule_strict_src(async_ipr, priority, spec):
    netns = async_ipr.status['netns']
    await async_ipr.rule('add', priority=priority, **spec)
    assert rule_exists(priority=priority, netns=netns)
