import os
from functools import partial
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from pyroute2 import netns
from pyroute2.common import uifname
from pyroute2.conntrack import AsyncConntrack, ConntrackEntry
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTAttrTuple


class ArgMeta(type):
    @property
    def NONE(cls) -> None:
        return None

    @property
    def AUTO(cls) -> str:
        return uifname()


class ArgNetNS(metaclass=ArgMeta):
    pass


@pytest_asyncio.fixture
async def ct(request):
    nsname = getattr(request, 'param', None)
    async with AsyncConntrack(netns=nsname) as s:
        yield s
    if nsname is not None:
        netns.remove(nsname)


@pytest.mark.asyncio
async def test_dump(ct):
    dump = await ct.dump_entries()
    assert isinstance(dump, AsyncGenerator)
    async for entry in dump:
        assert isinstance(entry, ConntrackEntry)
        assert isinstance(entry.tuple_orig.saddr, str)
        assert isinstance(entry.tuple_orig.proto, int)


@pytest.mark.parametrize(
    ('ct', 'check_stat'),
    (
        (ArgNetNS.NONE, lambda i: any(map(lambda x: x.get('insert') > 0, i))),
        (ArgNetNS.AUTO, lambda i: all(map(lambda x: x.get('insert') == 0, i))),
    ),
    indirect=('ct',),
)
@pytest.mark.asyncio
async def test_stat(ct, check_stat):
    stat = await ct.stat()
    assert len(stat) == os.cpu_count()
    assert check_stat(stat)


async def entry_locate(target, ct):
    ret = False
    async for entry in await ct.dump_entries():
        if (
            entry.tuple_orig.saddr == '10.1.2.3'
            and entry.tuple_orig.proto == 6
            and entry.tuple_orig.sport == 12345
        ):
            ret = True
            break
    assert ret is target


async def entry_count(func, ct):
    count = await ct.count()
    assert isinstance(count, int)
    assert func(count)


async def entry_op(cmd, ct):
    await ct.entry(
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


@pytest.mark.parametrize(
    ('ct', 'steps'),
    (
        (
            ArgNetNS.NONE,
            (
                partial(entry_op, 'add'),
                partial(entry_locate, True),
                partial(entry_op, 'del'),
                partial(entry_locate, False),
            ),
        ),
        (
            ArgNetNS.AUTO,
            (
                partial(entry_op, 'add'),
                partial(entry_locate, True),
                partial(entry_op, 'del'),
                partial(entry_locate, False),
            ),
        ),
        (
            ArgNetNS.NONE,
            (
                partial(entry_op, 'add'),
                partial(entry_count, lambda x: x > 0),
                partial(entry_op, 'del'),
            ),
        ),
        (
            ArgNetNS.AUTO,
            (
                partial(entry_count, lambda x: x == 0),
                partial(entry_op, 'add'),
                partial(entry_count, lambda x: x == 1),
                partial(entry_op, 'del'),
                partial(entry_count, lambda x: x == 0),
            ),
        ),
    ),
    indirect=('ct',),
    ids=('locate', 'locate (netns)', 'count', 'count (netns)'),
)
@pytest.mark.asyncio
async def test_op(ct, steps):
    for step in steps:
        await step(ct)
