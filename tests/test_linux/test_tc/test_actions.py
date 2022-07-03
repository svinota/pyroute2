import pytest
from pr2test.context_manager import make_test_matrix, skip_if_not_supported
from pr2test.marks import require_root

from pyroute2 import protocols

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


def find_action(context, prio=1, filter_name="u32"):
    """Returns the first action with priority `prio`
    under the filter with `filter_name`
    """
    # Fetch filters
    filts = context.ipr.get_filters(index=context.default_interface.index)
    # Find our action
    for i in filts:
        try:
            act = (
                i.get_attr('TCA_OPTIONS')
                .get_attr('TCA_%s_ACT' % filter_name.upper())
                .get_attr('TCA_ACT_PRIO_%d' % prio)
            )
            assert act
            return act
        except AttributeError:
            continue
    raise FileNotFoundError('Action not found')


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_mirred(context):
    index, ifname = context.default_interface
    # add a htb root
    context.ipr.tc('add', 'htb', index=index, handle='1:', default='20:0')
    # mirred action
    actions = [
        dict(
            kind='mirred', direction='egress', action='mirror', ifindex=index
        ),
        dict(
            kind='mirred', direction='egress', action='redirect', ifindex=index
        ),
    ]
    # create a filter with this action
    context.ipr.tc(
        'add-filter',
        'u32',
        index=index,
        handle='0:0',
        parent='1:0',
        prio=10,
        protocol=protocols.ETH_P_IP,
        target='1:10',
        keys=['0x0006/0x00ff+8'],
        action=actions,
    )

    # Check that we have two mirred actions with the right parameters
    act = find_action(context, 1)
    assert act.get_attr('TCA_ACT_KIND') == 'mirred'
    parms = act.get_attr('TCA_ACT_OPTIONS').get_attr('TCA_MIRRED_PARMS')
    assert parms['eaction'] == 2  # egress mirror, see act_mirred.py
    assert parms['ifindex'] == index
    assert parms['action'] == 3  # TC_ACT_PIPE because action == mirror

    act = find_action(context, 2)
    assert act.get_attr('TCA_ACT_KIND') == 'mirred'
    parms = act.get_attr('TCA_ACT_OPTIONS').get_attr('TCA_MIRRED_PARMS')
    assert parms['eaction'] == 1  # egress redirect, see act_mirred.py
    assert parms['ifindex'] == index
    assert parms['action'] == 4  # TC_ACT_STOLEN because action == redirect


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_connmark(context):
    index, ifname = context.default_interface
    # add a htb root
    context.ipr.tc('add', 'htb', index=index, handle='1:', default='20:0')
    # connmark action
    action = {'kind': 'connmark', 'zone': 63}
    # create a filter with this action
    context.ipr.tc(
        'add-filter',
        'u32',
        index=index,
        handle='0:0',
        parent='1:0',
        prio=10,
        protocol=protocols.ETH_P_IP,
        target='1:10',
        keys=['0x0006/0x00ff+8'],
        action=action,
    )

    act = find_action(context)

    # Check that it is a connmark action with the right parameters
    assert act.get_attr('TCA_ACT_KIND') == 'connmark'
    parms = act.get_attr('TCA_ACT_OPTIONS').get_attr('TCA_CONNMARK_PARMS')
    assert parms['zone'] == 63
