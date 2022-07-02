import collections
import json
import subprocess

import pytest
from pr2test.marks import require_root

from pyroute2 import NDB
from pyroute2.common import dqn2int, hexdump, hexload
from pyroute2.dhcp import client

pytestmark = [require_root()]


@pytest.fixture
def ctx():
    ndb = NDB()
    index = 0
    ifname = ''
    # get a DHCP default route, if exists
    for route in ndb.routes.dump().filter(proto=16, dst=''):
        index = route.oif
        ifname = ndb.interfaces[index]['ifname']
    yield collections.namedtuple('Context', ['ndb', 'index', 'ifname'])(
        ndb, index, ifname
    )
    ndb.close()


def test_client_module(ctx):
    if ctx.index == 0:
        pytest.skip('no DHCP interfaces detected')

    response = client.action(ctx.ifname)
    options = response['options']
    router = response['options']['router'][0]
    prefixlen = dqn2int(response['options']['subnet_mask'])
    address = response['yiaddr']
    l2addr = response['chaddr']

    # convert addresses like 96:0:1:45:fa:6c into 96:00:01:45:fa:6c
    assert (
        hexdump(hexload(l2addr)) == ctx.ndb.interfaces[ctx.ifname]['address']
    )
    assert router == ctx.ndb.routes['default']['gateway']
    assert {
        'address': address,
        'prefixlen': prefixlen,
        'index': ctx.index,
    } in ctx.ndb.addresses
    assert options['lease_time'] > 0
    assert options['rebinding_time'] > 0
    assert options['renewal_time'] > 0
    return response


def test_client_console(ctx):
    response_from_module = json.loads(json.dumps(test_client_module(ctx)))
    client = subprocess.run(
        ['pyroute2-dhcp-client', ctx.ifname], stdout=subprocess.PIPE
    )
    response_from_console = json.loads(client.stdout)
    assert response_from_module == response_from_console
