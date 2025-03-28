import subprocess
from collections import namedtuple

import pytest

from pyroute2 import AsyncNFTSocket, NFTSocket
from pyroute2.common import uifname
from pyroute2.netlink.nfnetlink import nfgen_msg
from pyroute2.netlink.nfnetlink.nftsocket import (
    NFT_MSG_GETCHAIN,
    NFT_MSG_GETTABLE,
)

NFTSetup = namedtuple('NFTSetup', ('table', 'chain'))

list_objects = pytest.mark.parametrize(
    'cmd,get_field',
    (
        (NFT_MSG_GETTABLE, lambda x: x.table),
        (NFT_MSG_GETCHAIN, lambda x: x.chain),
    ),
    ids=['table', 'chain'],
)


@pytest.fixture
def nft():
    table = uifname()
    chain = uifname()
    subprocess.call(f'nft add table {table}'.split())
    subprocess.call(
        f'nft add chain {table} {chain} '
        f'{{ type filter hook input priority 500 ; }}'.split()
    )
    yield NFTSetup(table, chain)
    subprocess.call(f'nft delete table {table}'.split())


@list_objects
def test_list_sync(nft, cmd, get_field):
    with NFTSocket() as sock:
        objects = [
            msg.get('name') for msg in sock.request_get(nfgen_msg(), cmd)
        ]
        assert get_field(nft) in objects


@list_objects
@pytest.mark.asyncio
async def test_list_async(nft, cmd, get_field):
    async with AsyncNFTSocket() as sock:
        objects = [
            msg.get('name')
            async for msg in await sock.request_get(nfgen_msg(), cmd)
        ]
        assert get_field(nft) in objects
