from pyroute2 import NetlinkError
from pr2test import custom_link_kind
from pr2test.custom_link_kind.foo import vlan as foo_vlan


def test_register_fail(context):
    ifname = context.new_ifname

    try:
        context.ipr.link(
            'add',
            ifname=ifname,
            link=context.default_interface[0],
            kind='vlan',
            foo_id=101,
        )
    except NetlinkError as e:
        if e.code == 22:  # Invalid argument
            return
    raise Exception('test failed')


def test_register_path(context):
    ifname = context.new_ifname

    old = context.ipr.list_link_kind()['vlan']
    context.ipr.register_link_kind(path='pytest/pr2test/custom_link_kind/')
    context.ipr.link(
        'add',
        ifname=ifname,
        link=context.default_interface[0],
        kind='vlan',
        foo_id=101,
    )
    assert (
        context.ipr.link('get', ifname=ifname)[0].get_nested(
            'IFLA_LINKINFO', 'IFLA_INFO_DATA', 'IFLA_FOO_ID'
        )
        == 101
    )
    context.ipr.register_link_kind(module={'vlan': old})


def test_register_pkg(context):
    ifname = context.new_ifname

    old = context.ipr.list_link_kind()['vlan']
    context.ipr.register_link_kind(pkg=custom_link_kind)
    context.ipr.link(
        'add',
        ifname=ifname,
        link=context.default_interface[0],
        kind='vlan',
        foo_id=101,
    )
    assert (
        context.ipr.link('get', ifname=ifname)[0].get_nested(
            'IFLA_LINKINFO', 'IFLA_INFO_DATA', 'IFLA_FOO_ID'
        )
        == 101
    )
    context.ipr.register_link_kind(module={'vlan': old})


def test_register_module(context):
    ifname = context.new_ifname

    old = context.ipr.list_link_kind()['vlan']
    context.ipr.register_link_kind(module={'vlan': foo_vlan})
    context.ipr.link(
        'add',
        ifname=ifname,
        link=context.default_interface[0],
        kind='vlan',
        foo_id=101,
    )
    assert (
        context.ipr.link('get', ifname=ifname)[0].get_nested(
            'IFLA_LINKINFO', 'IFLA_INFO_DATA', 'IFLA_FOO_ID'
        )
        == 101
    )
    context.ipr.register_link_kind(module={'vlan': old})
