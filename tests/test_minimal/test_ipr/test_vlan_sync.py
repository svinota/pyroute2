import pytest

from pyroute2.common import uifname


@pytest.mark.parametrize(
    'flags,option,check',
    (
        (1, 'entry', lambda x: x.get(('info', 'vid')) == 1),
        (2, 'global_options', lambda x: x.get('id') == 1),
    ),
)
def test_vlan_dumpdb(sync_ipr, flags, option, check):
    sync_ipr.ensure(sync_ipr.link, ifname=uifname(), kind='bridge', state='up')
    breakpoint()
    for response in sync_ipr.vlandb('dump', dump_flags=flags):
        for vlan in response.get_attrs(option):
            assert check(vlan)
        break
    else:
        raise Exception('no vlan info dumped')
