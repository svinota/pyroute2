import errno
import socket
import time

import pytest
from pr2test.context_manager import skip_if_not_supported
from pr2test.marks import require_root
from utils import require_kernel

from pyroute2 import IPRoute, NetlinkError
from pyroute2.common import AF_MPLS
from pyroute2.netlink.rtnl.rtmsg import RTNH_F_ONLINK

pytestmark = [require_root()]


def test_route_get_target_strict_check(context):
    if not context.ipr.get_default_routes(table=254):
        pytest.skip('no default IPv4 routes')
    require_kernel(4, 20)
    with IPRoute(strict_check=True) as ip:
        rts = ip.get_routes(family=socket.AF_INET, dst='8.8.8.8', table=254)
        assert len(tuple(rts)) > 0


def test_extended_error_on_route(context):
    require_kernel(4, 20)
    # specific flags, cannot use context.ip
    with IPRoute(ext_ack=True, strict_check=True) as ip:
        with pytest.raises(NetlinkError) as e:
            ip.route("get", dst="1.2.3.4", table=254, dst_len=0)
    assert abs(e.value.code) == errno.EINVAL
    # on 5.10 kernel, full message is 'ipv4: rtm_src_len and
    # rtm_dst_len must be 32 for IPv4'
    assert "rtm_dst_len" in str(e.value)


@pytest.mark.parametrize(
    'proto', (('static', 'boot'), (4, 3), ('boot', 4), (3, 'static'))
)
def test_route_proto(context, proto):

    proto, fake = proto
    ipaddr = context.new_ipaddr
    gateway = context.new_ipaddr
    ipnet = context.new_ip4net
    ifname = context.new_ifname

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(f'{ipaddr}/24')
        .commit()
    )
    spec = {
        'dst': ipnet.network,
        'dst_len': ipnet.netmask,
        'gateway': gateway,
        'proto': proto,
    }
    context.ndb.routes.create(**spec).commit()

    with pytest.raises(NetlinkError):
        context.ipr.route(
            'del',
            dst=f'{ipnet.network}/{ipnet.netmask}',
            gateway=f'{gateway}',
            proto=fake,
        )
    context.ipr.route(
        'del',
        dst=f'{ipnet.network}/{ipnet.netmask}',
        gateway=f'{gateway}',
        proto=proto,
    )


def test_route_oif_as_iterable(context):
    index, ifname = context.default_interface
    ipnet = context.new_ip4net
    spec = {'dst': ipnet.network, 'dst_len': ipnet.netmask, 'oif': (index,)}
    context.ndb.interfaces[ifname].set('state', 'up').commit()
    context.ipr.route('add', **spec)
    route = context.ndb.routes.wait(
        dst=ipnet.network, dst_len=ipnet.netmask, timeout=5
    )
    assert route['oif'] == index


def test_route_get_target(context):
    if not context.ipr.get_default_routes(table=254):
        pytest.skip('no default IPv4 routes')
    rts = context.ipr.get_routes(
        family=socket.AF_INET, dst='8.8.8.8', table=254
    )
    assert len(tuple(rts)) > 0


def test_route_get_target_default_ipv4(context):
    rts = context.ipr.get_routes(dst='127.0.0.1')
    assert len(tuple(rts)) > 0


def test_route_get_target_default_ipv6(context):
    rts = context.ipr.get_routes(dst='::1')
    assert len(tuple(rts)) > 0


@skip_if_not_supported
@pytest.mark.parametrize('family', (socket.AF_INET, socket.AF_INET6))
def test_route_mpls_via(context, family):
    if family == socket.AF_INET:
        address = context.new_ipaddr
    else:
        ip6net = context.new_ip6net
        address = str(ip6net.network) + '7c32'
    label = 0x20
    index, ifname = context.default_interface
    context.ndb.interfaces[ifname].set('state', 'up').commit()
    context.ipr.route(
        'add',
        **{
            'family': AF_MPLS,
            'oif': index,
            'via': {'family': family, 'addr': address},
            'newdst': {'label': label, 'bos': 1},
        },
    )

    rt = tuple(context.ipr.get_routes(oif=index, family=AF_MPLS))[0]
    assert rt.get_attr('RTA_VIA')['addr'] == address
    assert rt.get_attr('RTA_VIA')['family'] == family
    assert rt.get_attr('RTA_NEWDST')[0]['label'] == label
    assert len(rt.get_attr('RTA_NEWDST')) == 1
    context.ipr.route(
        'del',
        **{
            'family': AF_MPLS,
            'oif': index,
            'dst': {'label': 0x10, 'bos': 1},
            'via': {'family': family, 'addr': address},
            'newdst': {'label': label, 'bos': 1},
        },
    )
    assert len(tuple(context.ipr.get_routes(oif=index, family=AF_MPLS))) == 0


@skip_if_not_supported
@pytest.mark.parametrize(
    'newdst', ({'label': 0x21, 'bos': 1}, [{'label': 0x21, 'bos': 1}])
)
def test_route_mpls_swap_newdst(context, newdst):
    index, _ = context.default_interface
    req = {
        'family': AF_MPLS,
        'oif': index,
        'dst': {'label': 0x20, 'bos': 1},
        'newdst': newdst,
    }
    context.ipr.route('add', **req)

    rt = tuple(context.ipr.get_routes(oif=index, family=AF_MPLS))[0]
    assert rt.get_attr('RTA_DST')[0]['label'] == 0x20
    assert len(rt.get_attr('RTA_DST')) == 1
    assert rt.get_attr('RTA_NEWDST')[0]['label'] == 0x21
    assert len(rt.get_attr('RTA_NEWDST')) == 1
    context.ipr.route('del', **req)
    assert len(tuple(context.ipr.get_routes(oif=index, family=AF_MPLS))) == 0


@pytest.mark.parametrize('mode', ('normal', 'raw'))
def test_route_multipath(context, mode):
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ip4net = context.new_ip4net

    if mode == 'normal':
        multipath = [{'gateway': gateway1}, {'gateway': gateway2}]
    elif mode == 'raw':
        multipath = [
            {'hops': 20, 'oif': index, 'attrs': [['RTA_GATEWAY', gateway1]]},
            {'hops': 30, 'oif': index, 'attrs': [['RTA_GATEWAY', gateway2]]},
        ]

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    context.ipr.route(
        'add', dst=ip4net.network, dst_len=ip4net.netmask, multipath=multipath
    )

    route = context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, timeout=5
    )
    nh1 = route['multipath'][0]
    nh2 = route['multipath'][1]

    assert nh1['gateway'] == gateway1
    assert nh2['gateway'] == gateway2


@pytest.mark.parametrize('flags', (RTNH_F_ONLINK, ['onlink']))
def test_route_onlink(context, flags):
    ip4net = context.new_ip4net
    ipaddr = context.new_ipaddr
    index, ifname = context.default_interface

    context.ipr.route(
        'add',
        dst=ip4net.network,
        dst_len=ip4net.netmask,
        gateway=ipaddr,
        oif=index,
        flags=flags,
    )
    route = context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, timeout=5
    )
    assert route['oif'] == index
    route.remove().commit()


@pytest.mark.parametrize('flags', (RTNH_F_ONLINK, ['onlink']))
def test_route_onlink_multipath(context, flags):
    ip4net = context.new_ip4net
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    index, ifname = context.default_interface
    context.ipr.route(
        'add',
        dst=ip4net.network,
        dst_len=ip4net.netmask,
        multipath=[
            {'gateway': gateway1, 'oif': 1, 'flags': flags},
            {'gateway': gateway2, 'oif': 1, 'flags': flags},
        ],
    )

    route = context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, timeout=5
    )
    nh1 = route['multipath'][0]
    nh2 = route['multipath'][1]

    assert nh1['gateway'] == gateway1
    assert nh2['gateway'] == gateway2

    route.remove().commit()


@skip_if_not_supported
def _test_lwtunnel_multipath_mpls(context):
    ip4net = context.new_ip4net
    index, ifname = context.default_interface
    gateway = context.new_ipaddr
    ipaddr = context.new_ipaddr

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()

    context.ipr.route(
        'add',
        dst=f'{ip4net.network}/{ip4net.netmask}',
        multipath=[
            {'encap': {'type': 'mpls', 'labels': 500}, 'oif': index},
            {
                'encap': {'type': 'mpls', 'labels': '600/700'},
                'gateway': gateway,
            },
        ],
    )

    routes = tuple(
        context.ipr.route('dump', dst=ip4net.network, dst_len=ip4net.netmask)
    )
    assert len(routes) == 1
    mp = routes[0].get_attr('RTA_MULTIPATH')
    assert len(mp) == 2
    assert mp[0]['oif'] == 1
    assert mp[0].get_attr('RTA_ENCAP_TYPE') == 1
    labels = mp[0].get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
    assert len(labels) == 1
    assert labels[0]['bos'] == 1
    assert labels[0]['label'] == 500
    assert mp[1].get_attr('RTA_ENCAP_TYPE') == 1
    labels = mp[1].get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
    assert len(labels) == 2
    assert labels[0]['bos'] == 0
    assert labels[0]['label'] == 600
    assert labels[1]['bos'] == 1
    assert labels[1]['label'] == 700


@skip_if_not_supported
@pytest.mark.parametrize(
    'lid,lnum,labels',
    (
        ('list+dict', 2, [{'bos': 0, 'label': 226}, {'bos': 1, 'label': 227}]),
        ('list+int', 2, [226, 227]),
        ('str', 2, '226/227'),
        ('list+dict', 1, [{'bos': 1, 'label': 227}]),
        ('list+int', 1, [227]),
        ('str', 1, '227'),
        ('dict', 1, {'bos': 1, 'label': 227}),
        ('int', 1, 227),
    ),
)
def test_lwtunnel_mpls_labels(context, lid, lnum, labels):
    ip4net = context.new_ip4net
    ipaddr = context.new_ipaddr
    gateway = context.new_ipaddr
    index, ifname = context.default_interface
    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    context.ipr.route(
        'add',
        dst=ip4net.network,
        dst_len=ip4net.netmask,
        encap={'type': 'mpls', 'labels': labels},
        gateway=gateway,
    )
    routes = tuple(
        context.ipr.route('dump', dst=ip4net.network, dst_len=ip4net.netmask)
    )
    assert len(routes) == 1
    route = routes[0]
    assert route.get_attr('RTA_ENCAP_TYPE') == 1
    assert route.get_attr('RTA_GATEWAY') == gateway
    labels = route.get_attr('RTA_ENCAP').get_attr('MPLS_IPTUNNEL_DST')
    assert len(labels) == lnum
    if lnum == 2:
        assert labels[0]['bos'] == 0
        assert labels[0]['label'] == 226
        assert labels[1]['bos'] == 1
        assert labels[1]['label'] == 227
    else:
        assert labels[0]['bos'] == 1
        assert labels[0]['label'] == 227

    context.ipr.route('del', dst=f'{ip4net.network}/{ip4net.netmask}')


def test_route_change_existing(context):

    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ip4net = context.new_ip4net

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    context.ipr.route(
        'add', dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway1
    )
    context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway1, timeout=5
    )

    context.ipr.route(
        'change', dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2
    )
    context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2, timeout=5
    )


def test_route_change_not_existing_fail(context):
    # route('change', ...) should fail, if no route exists
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ip4net = context.new_ip4net

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()

    with pytest.raises(NetlinkError) as e:
        context.ipr.route(
            'change',
            dst=ip4net.network,
            dst_len=ip4net.netmask,
            gateway=gateway2,
        )
    assert e.value.code == errno.ENOENT


def test_route_replace_existing(context):
    # route('replace', ...) should succeed, if route exists
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ip4net = context.new_ip4net

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    context.ipr.route(
        'add', dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway1
    )
    context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway1, timeout=5
    )

    context.ipr.route(
        'replace', dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2
    )
    context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2, timeout=5
    )


def test_route_replace_not_existing(context):
    # route('replace', ...) should succeed, if route doesn't exist
    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ip4net = context.new_ip4net

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    context.ipr.route(
        'replace', dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2
    )
    context.ndb.routes.wait(
        dst=ip4net.network, dst_len=ip4net.netmask, gateway=gateway2, timeout=5
    )


def test_flush_routes(context):

    index, ifname = context.default_interface
    ipaddr = context.new_ipaddr
    gateway = context.new_ipaddr

    context.ndb.interfaces[ifname].add_ip(f'{ipaddr}/24').commit()
    for net in [context.new_ip4net for _ in range(10)]:
        context.ipr.route(
            'add',
            dst=net.network,
            dst_len=net.netmask,
            gateway=gateway,
            table=10101,
            oif=index,
        )
        context.ndb.routes.wait(
            dst=net.network, dst_len=net.netmask, table=10101, timeout=5
        )

    with context.ndb.routes.summary() as summary:
        summary.select_records(table=10101)
        assert len(tuple(summary)) == 10
    context.ipr.flush_routes(table=10101, family=socket.AF_INET6)
    with context.ndb.routes.summary() as summary:
        summary.select_records(table=10101)
        assert len(tuple(summary)) == 10
    context.ipr.flush_routes(table=10101, family=socket.AF_INET)
    for _ in range(5):
        with context.ndb.routes.summary() as summary:
            summary.select_records(table=10101)
            if len(tuple(summary)) == 0:
                break
        time.sleep(0.1)
    else:
        raise Exception('route table not flushed')
