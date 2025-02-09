import io
from socket import AF_INET, AF_INET6, AF_UNSPEC

import pytest
from net_tools import address_exists, route_exists

from pyroute2.common import load_dump

test_dump_data = '''

# 10.1.2.0/24 via 127.0.0.8 dev lo table 100
# 10.1.3.0/24 via 127.0.0.8 dev lo table 100

24:12:31:45  3c:00:00:00  18:00:22:00  dc:d0:86:67
7b:68:00:00  02:18:00:00  64:03:00:01  00:00:00:00
08:00:0f:00  64:00:00:00  08:00:01:00  0a:01:02:00
08:00:05:00  7f:00:00:08  08:00:04:00  01:00:00:00
3c:00:00:00  18:00:22:00  dc:d0:86:67  7b:68:00:00
02:18:00:00  64:03:00:01  00:00:00:00  08:00:0f:00
64:00:00:00  08:00:01:00  0a:01:03:00  08:00:05:00
7f:00:00:08  08:00:04:00  01:00:00:00
'''


def test_load(sync_ipr, nsname):
    sync_ipr.link('set', index=1, state='up')
    assert address_exists('127.0.0.1', ifname='lo', netns=nsname)
    assert not route_exists(dst='10.1.2.0/24', table=100, netns=nsname)
    assert not route_exists(dst='10.1.3.0/24', table=100, netns=nsname)
    fd = io.BytesIO()
    fd.write(load_dump(test_dump_data))
    fd.seek(0)
    sync_ipr.route_load(fd)
    assert route_exists(dst='10.1.2.0/24', table=100, netns=nsname)
    assert route_exists(dst='10.1.3.0/24', table=100, netns=nsname)


def test_loads(sync_ipr, nsname):
    sync_ipr.link('set', index=1, state='up')
    assert address_exists('127.0.0.1', ifname='lo', netns=nsname)
    assert not route_exists(dst='10.1.2.0/24', table=100, netns=nsname)
    assert not route_exists(dst='10.1.3.0/24', table=100, netns=nsname)
    sync_ipr.route_loads(load_dump(test_dump_data))
    assert route_exists(dst='10.1.2.0/24', table=100, netns=nsname)
    assert route_exists(dst='10.1.3.0/24', table=100, netns=nsname)


@pytest.mark.parametrize(
    'family,target_tables,target_families,fmt,offset',
    [
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'iproute2', 4),
        (AF_INET, {254, 255}, {AF_INET}, 'iproute2', 4),
        (AF_INET6, {254, 255}, {AF_INET6}, 'iproute2', 4),
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'raw', 0),
        (AF_INET, {254, 255}, {AF_INET}, 'raw', 0),
        (AF_INET6, {254, 255}, {AF_INET6}, 'raw', 0),
    ],
    ids=(
        'iproute2/AF_UNSPEC',
        'iproute2/AF_INET',
        'iproute2/AF_INET6',
        'raw/AF_UNSPEC',
        'raw/AF_INET',
        'raw/AF_INET6',
    ),
)
def test_dump(sync_ipr, family, target_tables, target_families, fmt, offset):
    fd = io.BytesIO()
    sync_ipr.route_dump(fd, family=family, fmt=fmt)
    tables = set()
    families = set()
    for route in sync_ipr.marshal.parse(fd.getvalue()[offset:]):
        tables.add(route.get('table'))
        families.add(route.get('family'))
    assert tables <= target_tables
    assert families == target_families


@pytest.mark.parametrize(
    'family,target_tables,target_families,fmt,offset',
    [
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'iproute2', 4),
        (AF_INET, {254, 255}, {AF_INET}, 'iproute2', 4),
        (AF_INET6, {254, 255}, {AF_INET6}, 'iproute2', 4),
        (AF_UNSPEC, {254, 255}, {AF_INET, AF_INET6}, 'raw', 0),
        (AF_INET, {254, 255}, {AF_INET}, 'raw', 0),
        (AF_INET6, {254, 255}, {AF_INET6}, 'raw', 0),
    ],
    ids=(
        'iproute2/AF_UNSPEC',
        'iproute2/AF_INET',
        'iproute2/AF_INET6',
        'raw/AF_UNSPEC',
        'raw/AF_INET',
        'raw/AF_INET6',
    ),
)
def test_dumps(sync_ipr, family, target_tables, target_families, fmt, offset):
    data = sync_ipr.route_dumps(family=family, fmt=fmt)
    tables = set()
    families = set()
    for route in sync_ipr.marshal.parse(data[offset:]):
        tables.add(route.get('table'))
        families.add(route.get('family'))
    assert tables <= target_tables
    assert families == target_families
