import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from pyroute2 import AsyncNFCTSocket
from pyroute2.netlink import nlmsg
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTAttrTuple


@pytest_asyncio.fixture
async def nfct():
    async with AsyncNFCTSocket() as s:
        yield s


@pytest.mark.asyncio
async def test_dump(nfct):
    dump = await nfct.dump()
    assert isinstance(dump, AsyncGenerator)
    async for msg in dump:
        assert isinstance(msg, nlmsg)
        assert isinstance(
            msg.get(('CTA_TUPLE_ORIG', 'CTA_TUPLE_IP', 'CTA_IP_V4_SRC')), str
        )
        assert isinstance(
            msg.get(('CTA_TUPLE_ORIG', 'CTA_TUPLE_PROTO', 'CTA_PROTO_NUM')),
            int,
        )


@pytest.mark.asyncio
async def test_count(nfct):
    (count,) = await nfct.count()
    assert isinstance(count.get('CTA_STATS_GLOBAL_ENTRIES'), int)
    assert isinstance(count.get('CTA_STATS_GLOBAL_MAX_ENTRIES'), int)


@pytest.mark.asyncio
async def test_stat(nfct):
    stat = await nfct.stat()
    assert len(stat) == os.cpu_count()
    assert all(map(lambda x: isinstance(x, nlmsg), stat))
    assert any(map(lambda x: x.get('insert') > 0, stat))


async def locate_entry(nfct):
    async for msg in await nfct.dump():
        if (
            msg.get(('tuple_orig', 'ip', 'v4_src')) == '10.1.2.3'
            and msg.get(('tuple_orig', 'proto', 'num')) == 6
            and msg.get(('tuple_orig', 'proto', 'src_port')) == 12345
        ):
            return True
    return False


@pytest.mark.parametrize('cmd,entry_exists', (('add', True), ('del', False)))
@pytest.mark.asyncio
async def _test_entry(nfct, cmd, entry_exists):
    await nfct.entry(
        cmd,
        timeout=10,
        tuple_orig=NFCTAttrTuple(
            saddr='10.1.2.3',
            daddr='10.3.2.1',
            proto=6,
            sport=12345,
            dport=54321,
        ),
        tuple_reply=NFCTAttrTuple(
            saddr='10.3.2.1',
            daddr='10.1.2.3',
            proto=6,
            sport=54321,
            dport=12345,
        ),
    )
    assert await locate_entry(nfct) is entry_exists
