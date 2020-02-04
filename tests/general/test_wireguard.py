from pyroute2 import NDB
from pyroute2 import WireGuard
from pyroute2.common import uifname
from utils import grep
from utils import require_user
from utils import allocate_network
from utils import free_network
from utils import skip_if_not_supported


class TestBasic(object):

    @skip_if_not_supported
    def setup(self):
        require_user('root')
        self.ifnames = []
        self.ipnets = []
        self.ifnames.append(uifname())
        self.ipnets.append(allocate_network())
        self.ipnets.append(allocate_network())
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        with NDB() as ndb:
            (ndb
             .interfaces
             .create(ifname=self.ifnames[0], kind='wireguard')
             .add_ip('%s/24' % (self.ipranges[0][1]))
             .commit())
        self.wg = WireGuard()

    def teardown(self):
        with NDB() as ndb:
            for i in self.ifnames:
                (ndb
                 .interfaces[i]
                 .remove()
                 .commit())
        for net in self.ipnets:
            free_network(net)

    def test_set_peer(self):
        peer = {'public_key': 'TGFHcm9zc2VCaWNoZV9DJ2VzdExhUGx1c0JlbGxlPDM=',
                'endpoint_addr': self.ipranges[1][1],
                'endpoint_port': 8888,
                'persistent_keepalive': 15,
                'allowed_ips': ['%s/24' % self.ipranges[0][0],
                                '%s/24' % self.ipranges[1][0]]}

        self.wg.set(self.ifnames[0],
                    private_key='RCdhcHJlc0JpY2hlLEplU2VyYWlzTGFQbHVzQm9ubmU=',
                    fwmark=0x1337,
                    listen_port=2525,
                    peer=peer)

        assert grep('wg show %s' % self.ifnames[0],
                    pattern='peer: %s' % peer['public_key'])
