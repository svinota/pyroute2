import os
from functools import partial
from typing import Generator

import pytest

from pyroute2 import netns
from pyroute2.common import uifname
from pyroute2.conntrack import Conntrack, ConntrackEntry
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


@pytest.fixture
def ct(request):
    nsname = getattr(request, 'param', None)
    with Conntrack(netns=nsname) as s:
        yield s
    if nsname is not None:
        netns.remove(nsname)


def test_dump(ct):
    dump = ct.dump_entries()
    assert isinstance(dump, Generator)
    for entry in dump:
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
def test_stat(ct, check_stat):
    stat = ct.stat()
    assert len(stat) == os.cpu_count()
    assert check_stat(stat)


def entry_locate(target, ct):
    ret = False
    for entry in ct.dump_entries():
        if (
            entry.tuple_orig.saddr == '10.1.2.3'
            and entry.tuple_orig.proto == 6
            and entry.tuple_orig.sport == 12345
        ):
            ret = True
            break
    assert ret is target


def entry_count(func, ct):
    count = ct.count()
    assert isinstance(count, int)
    assert func(count)


def entry_op(cmd, ct):
    ct.entry(
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
def test_op(ct, steps):
    for step in steps:
        step(ct)
