import pytest

from pyroute2 import IPRoute


@pytest.mark.parametrize('nlm_echo', (True, False))
def test_echo_route(context, nlm_echo):
    index, ifname = context.default_interface
    address = context.new_ipaddr
    gateway = context.get_ipaddr(r=0)
    target = context.get_ipaddr(r=1)
    spec = {'dst': target, 'dst_len': 32, 'gateway': gateway, 'oif': index}
    nla_check = {}
    for key, value in spec.items():
        nla_check[key] = value if nlm_echo else None
    with IPRoute(nlm_echo=nlm_echo) as ipr:
        context.ipr.addr('add', index=index, address=address, prefixlen=24)
        context.ipr.poll(context.ipr.addr, 'dump', address=address)
        response = tuple(ipr.route('add', **spec))[0]
        for key, value in nla_check.items():
            assert response.get(key) == value
