from socket import AF_INET

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root

from pyroute2 import protocols
from pyroute2.netlink.rtnl import TC_H_INGRESS, TC_H_ROOT

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_simple(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'ingress', index=index)
    qdisc = None
    for qdisc in context.ipr.get_qdiscs(index=index):
        if qdisc.get_attr('TCA_KIND') == 'ingress':
            break
    else:
        raise FileNotFoundError('qdisc not found')
    assert qdisc['handle'] == 0xFFFF0000
    assert qdisc['parent'] == TC_H_INGRESS
    return (index, ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_filter(context):
    index, ifname = test_simple(context)
    context.ipr.tc(
        'add-filter',
        'u32',
        index=index,
        protocol=AF_INET,
        parent=0xFFFF0000,
        action='drop',
        target=0x1,
        rate='10kbit',
        burst=10240,
        limit=0,
        prio=50,
        keys=['0x0/0x0+12'],
    )
    fls = context.ipr.get_filters(index=index, parent=0xFFFF0000)
    # assert there are filters
    assert fls
    # assert there is one police rule:
    prs = [
        x
        for x in fls
        if x.get_attr('TCA_OPTIONS') is not None
        and (
            x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_POLICE') is not None
            or x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_ACT') is not None
        )
    ][0]
    # assert the police rule has specified parameters
    options = prs.get_attr('TCA_OPTIONS')
    police_u32 = options.get_attr('TCA_U32_POLICE')
    # on modern kernels there is no TCA_U32_POLICE under
    # TCA_OPTIONS, but there is TCA_U32_ACT
    if police_u32 is None:
        police_u32 = (
            options.get_attr('TCA_U32_ACT')
            .get_attr('TCA_ACT_PRIO_0')
            .get_attr('TCA_ACT_OPTIONS')
        )
    police_tbf = police_u32.get_attr('TCA_POLICE_TBF')
    assert police_tbf['rate'] == 1250
    assert police_tbf['mtu'] == 2040


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_action_stats(context):
    index, ifname = test_simple(context)
    context.ipr.tc(
        'add-filter',
        'u32',
        index=index,
        parent='ffff:',
        protocol=protocols.ETH_P_ALL,
        keys=['0x0/0x0+0'],
        target=TC_H_ROOT,
        action={'kind': 'gact', 'action:': 'ok'},
    )
    fls = context.ipr.get_filters(index=index, parent=TC_H_INGRESS)

    act = [
        x
        for x in fls
        if x.get_attr('TCA_OPTIONS') is not None
        and (x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_ACT') is not None)
    ][0]
    # assert we have a u32 filter with a gact action
    assert act.get_attr('TCA_KIND') == 'u32'
    gact = (
        act.get_attr("TCA_OPTIONS")
        .get_attr("TCA_U32_ACT")
        .get_attr("TCA_ACT_PRIO_1")
    )
    assert gact.get_attr('TCA_ACT_KIND') == 'gact'
    # assert our gact has stats
    assert gact.get_attr('TCA_ACT_STATS')
