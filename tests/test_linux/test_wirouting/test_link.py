import pytest

from pyroute2.wirouting import WiRoute

pytestmark = [pytest.mark.asyncio]


async def test_get_links_view(tmp_link_ifname, nsname):
    async with WiRoute(netns=nsname) as wiroute:
        await wiroute.link("add", ifname=tmp_link_ifname, kind="dummy")

        links_must_be_found = ["lo", tmp_link_ifname]
        async for link in wiroute.get_links_view():
            try:
                links_must_be_found.remove(link.nlmsg.get_attr("IFLA_IFNAME"))
            except ValueError:
                pass

        assert (
            not links_must_be_found
        )  # Verify all link name removed because found
