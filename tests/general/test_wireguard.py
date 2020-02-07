import os
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
        self.ipnets = []
        self.wg = WireGuard()
        self.log_id = uifname()
        self.ndb = NDB(log='../ndb-%s-%s.log' % (os.getpid(), self.log_id),
                       rtnl_debug=True)
        self.netif = uifname()
        self.wg0if = uifname()
        self.wg1if = uifname()
        self.ifnames = [self.netif,
                        self.wg0if,
                        self.wg1if]
        self.ipnets.append(allocate_network())
        self.ipnets.append(allocate_network())
        self.ipranges = [[str(x) for x in net] for net in self.ipnets]
        # create the "network" interface
        (self.ndb
         .interfaces
         .create(ifname=self.netif, kind='dummy')
         .set('state', 'up')
         .add_ip('%s/24' % (self.ipranges[0][1]))
         .commit())
        # create one peer
        (self.ndb
         .interfaces
         .create(ifname=self.wg0if, kind='wireguard')
         .set('state', 'up')
         .add_ip('%s/24' % (self.ipranges[1][1]))
         .commit())
        # create another peer
        (self.ndb
         .interfaces
         .create(ifname=self.wg1if, kind='wireguard')
         .set('state', 'up')
         .add_ip('%s/24' % (self.ipranges[1][2]))
         .commit())

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
        # host A
        #
        # private key aPrZzfjeiNuy/oolBFkX4ClU3UjYzVemhK49TfZvMmU=
        # public key orXRcGaN/vxYm0fupIq/Q0ePQyDviyDRtAxAPNJMrA0=
        peerB = {'public_key': 'waDwFcRFnPzGJqgaYoV3P7V3NOji5QNPNjUGuBrwwTI=',
                 'endpoint_addr': self.ipranges[1][1],
                 'endpoint_port': 12453,
                 'persistent_keepalive': 15,
                 'allowed_ips': ['%s/24' % self.ipranges[0][0],
                                 '%s/24' % self.ipranges[1][0]]}

        self.wg.set(self.wg0if,
                    private_key='aPrZzfjeiNuy/oolBFkX4ClU3UjYzVemhK49TfZvMmU=',
                    listen_port=12452,
                    peer=peerB)
        # host B
        #
        # private key eHqiUofUM6A41mDVSTbBwFyfkDsVW7uEhv9A8romH2A=
        # public key waDwFcRFnPzGJqgaYoV3P7V3NOji5QNPNjUGuBrwwTI=
        peerA = {'public_key': 'orXRcGaN/vxYm0fupIq/Q0ePQyDviyDRtAxAPNJMrA0=',
                 'endpoint_addr': self.ipranges[1][1],
                 'endpoint_port': 12452,
                 'persistent_keepalive': 15,
                 'allowed_ips': ['%s/24' % self.ipranges[0][0],
                                 '%s/24' % self.ipranges[1][0]]}

        self.wg.set(self.wg1if,
                    private_key='eHqiUofUM6A41mDVSTbBwFyfkDsVW7uEhv9A8romH2A=',
                    listen_port=12453,
                    peer=peerA)

        assert grep('wg show %s' % self.wg0if,
                    pattern='peer: %s' % peerB['public_key'])
        assert grep('wg show %s' % self.wg0if,
                    pattern='endpoint: %s:%s' %
                    (peerB['endpoint_addr'], peerB['endpoint_port']))
        assert grep('wg show %s' % self.wg0if, pattern='transfer:')
