import io
from socket import AF_INET, AF_INET6, AF_UNSPEC

import pytest

from pyroute2 import AsyncIPRoute


@pytest.mark.parametrize(
    'family,target_tables,target_families,fmt,offset',
    [
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'iproute2', 4),
        (AF_INET, {254, 255}, {AF_INET}, 'iproute2', 4),
        (AF_INET6, {254, 255}, {AF_INET6}, 'iproute2', 4),
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, None, 0),
        (AF_INET, {254, 255}, {AF_INET}, None, 0),
        (AF_INET6, {254, 255}, {AF_INET6}, None, 0),
    ],
    ids=(
        'iproute2/AF_UNSPEC',
        'iproute2/AF_INET',
        'iproute2/AF_INET6',
        'native/AF_UNSPEC',
        'native/AF_INET',
        'native/AF_INET6',
    ),
)
@pytest.mark.asyncio
async def test_route_dump(
    async_ipr, family, target_tables, target_families, fmt, offset
):
    fd = io.BytesIO()
    await async_ipr.route_dump(fd, family=family, fmt=fmt)
    tables = set()
    families = set()
    for route in async_ipr.marshal.parse(fd.getvalue()[offset:]):
        tables.add(route.get('table'))
        families.add(route.get('family'))
    assert tables >= target_tables
    assert families == target_families


@pytest.mark.parametrize(
    'family,target_tables,target_families,fmt,offset',
    [
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'iproute2', 4),
        (AF_INET, {254, 255}, {AF_INET}, 'iproute2', 4),
        (AF_INET6, {254, 255}, {AF_INET6}, 'iproute2', 4),
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, None, 0),
        (AF_INET, {254, 255}, {AF_INET}, None, 0),
        (AF_INET6, {254, 255}, {AF_INET6}, None, 0),
    ],
    ids=(
        'iproute2/AF_UNSPEC',
        'iproute2/AF_INET',
        'iproute2/AF_INET6',
        'native/AF_UNSPEC',
        'native/AF_INET',
        'native/AF_INET6',
    ),
)
@pytest.mark.asyncio
async def test_route_dumps(
    async_ipr, family, target_tables, target_families, fmt, offset
):
    data = await async_ipr.route_dumps(family=family, fmt=fmt)
    tables = set()
    families = set()
    for route in async_ipr.marshal.parse(data[offset:]):
        tables.add(route.get('table'))
        families.add(route.get('family'))
    assert tables >= target_tables
    assert families == target_families


@pytest.mark.parametrize(
    "command,kwarg",
    [
        ("dump", {"table": 255}),
        ("show", {"table": 255}),
        ("dump", {"match": {"table": 255}}),
        ("show", {"match": {"table": 255}}),
    ],
)
@pytest.mark.asyncio
async def test_route_filter(async_ipr, command, kwarg):
    assert set(
        [
            route.get('table')
            async for route in await async_ipr.route(command, **kwarg)
        ]
    ) == set([255])


@pytest.mark.parametrize(
    "command,kwarg",
    [
        ("dump", {"table": 255, "family": 1}),
        ("show", {"table": 255, "family": 1}),
    ],
)
@pytest.mark.asyncio
async def test_route_filter_strict(command, kwarg):
    async with AsyncIPRoute(strict_check=True) as ipr:
        assert set(
            [
                route.get('table')
                async for route in await ipr.route(command, **kwarg)
            ]
        ) == set([255])
