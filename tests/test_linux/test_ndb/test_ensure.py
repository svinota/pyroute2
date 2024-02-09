import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists

pytestmark = [require_root()]
test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize(
    'host_link_attr,create,ensure',
    (
        (
            None,
            (
                {'kind': 'dummy', 'state': 'down'},
                {'kind': 'dummy', 'state': 'up'},
                None,
            ),
            (
                {'kind': 'dummy', 'state': 'up'},
                {'kind': 'dummy', 'state': 'up'},
                {'kind': 'dummy', 'state': 'up'},
            ),
        ),
        (
            'link',
            (
                {
                    'kind': 'vlan',
                    'link': None,
                    'vlan_id': 1010,
                    'state': 'down',
                },
                {'kind': 'vlan', 'link': None, 'vlan_id': 1011, 'state': 'up'},
                None,
            ),
            (
                {'kind': 'vlan', 'link': None, 'vlan_id': 1010, 'state': 'up'},
                {'kind': 'vlan', 'link': None, 'vlan_id': 1011, 'state': 'up'},
                {'kind': 'vlan', 'link': None, 'vlan_id': 1012, 'state': 'up'},
            ),
        ),
        (
            'vxlan_link',
            (
                {
                    'kind': 'vxlan',
                    'vxlan_link': None,
                    'vxlan_id': 2020,
                    'state': 'down',
                },
                {
                    'kind': 'vxlan',
                    'vxlan_link': None,
                    'vxlan_id': 2021,
                    'state': 'up',
                },
                None,
            ),
            (
                {
                    'kind': 'vxlan',
                    'vxlan_link': None,
                    'vxlan_id': 2020,
                    'state': 'up',
                },
                {
                    'kind': 'vxlan',
                    'vxlan_link': None,
                    'vxlan_id': 2021,
                    'state': 'up',
                },
                {
                    'kind': 'vxlan',
                    'vxlan_link': None,
                    'vxlan_id': 2022,
                    'state': 'up',
                },
            ),
        ),
    ),
    ids=('dummy', 'vlan', 'vxlan'),
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_ensure_interface_simple(context, host_link_attr, create, ensure):
    # if we need a host interface
    if host_link_attr is not None:
        host_ifname = context.new_ifname
        host_nic = context.ndb.interfaces.create(
            ifname=host_ifname, kind='dummy', state='up'
        )
        host_nic.commit()
        for spec in create + ensure:
            if spec is not None:
                spec[host_link_attr] = host_nic['index']

    # patch interface specs
    for spec_create, spec_ensure in zip(create, ensure):
        ifname = context.new_ifname
        if spec_create is not None:
            spec_create['ifname'] = ifname
        if spec_ensure is not None:
            spec_ensure['ifname'] = ifname

    # create interfaces
    for spec in create:
        if spec is not None:
            context.ndb.interfaces.create(**spec).commit()

    # ensure interfaces
    for spec in ensure:
        if spec is not None:
            context.ndb.interfaces.ensure(**spec).commit()
            assert interface_exists(context.netns, **spec)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_ensure_ensure_ip(context):
    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    nic = context.ndb.interfaces.create(
        ifname=ifname, kind='dummy', state='down'
    )
    nic.add_ip(address=ipaddr1, prefixlen=24)
    nic.commit()

    (
        context.ndb.interfaces.ensure(ifname=ifname, kind='dummy', state='up')
        .ensure_ip(address=ipaddr1, prefixlen=24)
        .ensure_ip(address=ipaddr2, prefixlen=24)
        .commit()
    )
    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr2)
