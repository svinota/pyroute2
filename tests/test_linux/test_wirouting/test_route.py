from ipaddress import IPv4Network

import pytest

from pyroute2.wirouting import WiRoute

pytestmark = [pytest.mark.asyncio]


async def test_get_ipv4_routes_for():
    async for route in WiRoute().get_ipv4_routes_for("8.8.8.8/32"):
        assert route.dest == IPv4Network('8.8.8.8/32')
        link = await WiRoute().get_link_view(index=route.oif)
        assert route.oifname == link.name
        assert not route.is_default_route()
        assert route.rt_type_name == "unicast"
