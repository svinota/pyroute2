from pyroute2 import IPBatch
from pyroute2 import IPRoute
from pyroute2.common import uifname
from utils import require_user
from utils import allocate_network
from utils import free_network


class TestIPBatch(object):

    def setup(self):
        self.ipnet = allocate_network()
        self.iprange = [str(x) for x in self.ipnet]

    def teardown(self):
        free_network(self.ipnet)

    def ifaddr(self):
        return str(self.iprange.pop())

    def test_link_add(self):
        require_user('root')

        ifname = uifname()
        ipb = IPBatch()
        ipb.link('add', ifname=ifname, kind='dummy')
        data = ipb.batch
        ipb.reset()

        ipr = IPRoute()
        ipr.sendto(data, (0, 0))

        idx = ipr.link_lookup(ifname=ifname)[0]
        ipr.link('del', index=idx)
        ipr.close()
