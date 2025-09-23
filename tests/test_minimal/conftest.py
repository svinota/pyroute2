import subprocess
from collections import namedtuple

import pytest

from pyroute2.common import uifname

NFTSetup = namedtuple('NFTSetup', ('table', 'chain'))


@pytest.fixture
def nft():
    table = uifname()
    chain = uifname()
    subprocess.call(f'nft add table {table}'.split())
    subprocess.call(
        f'nft add chain {table} {chain} '
        f'{{ type filter hook input priority 500 ; }}'.split()
    )
    subprocess.call(
        f'nft add chain {table} POSTROUTING '
        f'{{ type nat hook postrouting priority 100 ; }}'.split()
    )
    yield NFTSetup(table, chain)
    subprocess.call(f'nft delete table {table}'.split())


pytest_plugins = ['pyroute2.fixtures.iproute', 'pyroute2.fixtures.plan9']
