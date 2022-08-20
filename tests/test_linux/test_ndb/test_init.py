import uuid
from socket import AF_INET, AF_INET6

import pytest
from pr2test.marks import require_root

from pyroute2 import NDB
from pyroute2.netlink.rtnl import RTMGRP_IPV4_IFADDR, RTMGRP_LINK

pytestmark = [require_root()]


@pytest.mark.parametrize('kind', ('local', 'netns'))
def test_netlink_groups(kind):
    spec = {
        'target': 'localhost',
        'kind': kind,
        'groups': RTMGRP_LINK | RTMGRP_IPV4_IFADDR,
    }
    if kind == 'netns':
        spec['netns'] = str(uuid.uuid4())
    with NDB(sources=[spec]) as ndb:
        assert 'lo' in ndb.interfaces
        with ndb.interfaces['lo'] as lo:
            lo.set(state='up')
        addresses4 = ndb.addresses.dump()
        addresses4.select_records(family=AF_INET)
        assert addresses4.count() > 0
        addresses6 = ndb.addresses.dump()
        addresses6.select_records(family=AF_INET6)
        assert addresses6.count() == 0
        routes = ndb.routes.dump()
        assert routes.count() == 0
        neighbours = ndb.neighbours.dump()
        assert neighbours.count() == 0
