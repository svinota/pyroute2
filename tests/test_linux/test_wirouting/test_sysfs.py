import pytest

from pyroute2.wirouting.sysfs import InterfaceSysfs

pytestmark = [pytest.mark.asyncio]


async def test_virtual_interface():
    assert not InterfaceSysfs("lo").has_device()
    assert InterfaceSysfs("lo").is_virtual()
