import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root

pytestmark = [require_root()]

test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add(context):
    index, ifname = context.default_interface
    vlan_name = context.new_ifname
    vlan_id = 101

    context.ipr.link(
        'add', ifname=vlan_name, kind='vlan', link=index, vlan_id=vlan_id
    )
    (vlan,) = context.ipr.poll(context.ipr.link, 'dump', ifname=vlan_name)

    assert vlan.get('ifname') == vlan_name
    assert vlan.get('link') == index
    assert vlan.get(('linkinfo', 'data', 'vlan_id')) == vlan_id


@pytest.mark.parametrize(
    'spec,key,check',
    (
        (
            {'vlan_egress_qos': {'from': 0, 'to': 3}},
            ('linkinfo', 'data', 'vlan_egress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 3},
        ),
        (
            {'vlan_ingress_qos': {'from': 0, 'to': 4}},
            ('linkinfo', 'data', 'vlan_ingress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 4},
        ),
        (
            {
                'vlan_egress_qos': {
                    'attrs': (('IFLA_VLAN_QOS_MAPPING', {'from': 0, 'to': 5}),)
                }
            },
            ('linkinfo', 'data', 'vlan_egress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 5},
        ),
        (
            {
                'vlan_ingress_qos': {
                    'attrs': (('IFLA_VLAN_QOS_MAPPING', {'from': 0, 'to': 6}),)
                }
            },
            ('linkinfo', 'data', 'vlan_ingress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 6},
        ),
    ),
    ids=[
        'egress-short-0:3',
        'ingress-short-0:4',
        'egress-full-0:5',
        'egress-full-0:6',
    ],
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_qos_add(context, spec, key, check):
    index, ifname = context.default_interface
    vlan_name = context.new_ifname
    vlan_id = 101

    context.ipr.link(
        'add',
        ifname=vlan_name,
        kind='vlan',
        link=index,
        vlan_id=vlan_id,
        **spec
    )
    (vlan,) = context.ipr.poll(context.ipr.link, 'dump', ifname=vlan_name)

    assert vlan.get('ifname') == vlan_name
    assert vlan.get('link') == index
    assert vlan.get(('linkinfo', 'data', 'vlan_id')) == vlan_id
    assert vlan.get(key) == check


@pytest.mark.parametrize(
    'spec,key,check',
    (
        (
            {'vlan_egress_qos': {'from': 0, 'to': 3}},
            ('linkinfo', 'data', 'vlan_egress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 3},
        ),
        (
            {'vlan_ingress_qos': {'from': 0, 'to': 4}},
            ('linkinfo', 'data', 'vlan_ingress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 4},
        ),
        (
            {
                'vlan_egress_qos': {
                    'attrs': (('IFLA_VLAN_QOS_MAPPING', {'from': 0, 'to': 5}),)
                }
            },
            ('linkinfo', 'data', 'vlan_egress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 5},
        ),
        (
            {
                'vlan_ingress_qos': {
                    'attrs': (('IFLA_VLAN_QOS_MAPPING', {'from': 0, 'to': 6}),)
                }
            },
            ('linkinfo', 'data', 'vlan_ingress_qos', 'vlan_qos_mapping'),
            {'from': 0, 'to': 6},
        ),
    ),
    ids=[
        'egress-short-0:3',
        'ingress-short-0:4',
        'egress-full-0:5',
        'egress-full-0:6',
    ],
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_qos_set(context, spec, key, check):
    index, ifname = context.default_interface
    vlan_name = context.new_ifname
    vlan_id = 101

    context.ipr.link(
        'add', ifname=vlan_name, kind='vlan', link=index, vlan_id=vlan_id
    )
    (vlan,) = context.ipr.poll(context.ipr.link, 'dump', ifname=vlan_name)

    assert vlan.get('ifname') == vlan_name
    assert vlan.get('link') == index
    assert vlan.get(('linkinfo', 'data', 'vlan_id')) == vlan_id
    assert vlan.get(key) is None

    context.ipr.link('set', index=vlan['index'], kind='vlan', **spec)

    (vlan,) = context.ipr.poll(context.ipr.link, 'dump', ifname=vlan_name)

    assert vlan.get(key) == check
