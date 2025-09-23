import pytest

from pyroute2.common import uifname
from pyroute2.nftables.expressions import ipv4addr, masq, verdict
from pyroute2.nftables.main import AsyncNFTables, NFTables

MAGIC = 'pyroute2-テスト — pröva UTF-8 kommentar — '


@pytest.mark.parametrize(
    'get_chain,get_target',
    (
        (lambda x: 'POSTROUTING', lambda x: masq()),
        (lambda x: x.chain, lambda x: verdict(code=1)),
    ),
    ids=['masq', 'accept'],
)
@pytest.mark.asyncio
async def test_add_rule_async(nft, get_chain, get_target):
    global MAGIC
    magic = MAGIC + uifname()
    async with AsyncNFTables() as cmd:
        async for rule in await cmd.get_rules():
            if rule.get('userdata') == magic:
                raise RuntimeError('magic exists')

        await cmd.rule(
            'add',
            table=nft.table,
            chain=get_chain(nft),
            expressions=(ipv4addr(src='10.244.0.0/16'), get_target(nft)),
            userdata=magic,
        )

        async for rule in await cmd.get_rules():
            if rule.get('userdata') == magic:
                break
        else:
            raise RuntimeError('magic does not exist')


@pytest.mark.parametrize(
    'get_chain,get_target',
    (
        (lambda x: 'POSTROUTING', lambda x: masq()),
        (lambda x: x.chain, lambda x: verdict(code=1)),
    ),
    ids=['masq', 'accept'],
)
def test_add_rule_sync(nft, get_chain, get_target):
    global MAGIC
    magic = MAGIC + uifname()
    with NFTables() as cmd:
        for rule in cmd.get_rules():
            if rule.get('userdata') == magic:
                raise RuntimeError('magic exists')

        cmd.rule(
            'add',
            table=nft.table,
            chain=get_chain(nft),
            expressions=(ipv4addr(src='10.244.0.0/16'), get_target(nft)),
            userdata=magic,
        )

        for rule in cmd.get_rules():
            if rule.get('userdata') == magic:
                break
        else:
            raise RuntimeError('magic does not exist')
