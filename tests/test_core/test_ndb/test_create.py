import pytest
from net_tools import interface_exists


@pytest.mark.parametrize(
    'spec,check',
    (
        (
            lambda **s: {'kind': 'xfrm', 'xfrm_if_id': -1} | s,
            lambda ns, n: interface_exists(n, netns=ns),
        ),
    ),
    ids=('xfrm',),
)
def test_link_create(
    ndb, test_link_index, tmp_link_ifname, nsname, spec, check
):
    r = ndb.interfaces.create(
        **spec(xfrm_if_id=test_link_index, ifname=tmp_link_ifname)
    ).commit()
    assert r['xfrm_if_id'] == test_link_index
    assert r['index'] > 0
    assert check(nsname, tmp_link_ifname)
