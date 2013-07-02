import socket
from utils import require_user
from utils import grep
from pyroute2 import IPRoute
from pyroute2.netlink.iproute import RTM_NEWQDISC
from pyroute2.netlink.iproute import RTM_NEWTFILTER


class BasicTest(object):

    def setup(self):
        require_user('root')
        self.ip = IPRoute()
        self.ip.link('add',
                     index=0,
                     ifname='dummyX',
                     linkinfo={'attrs': [['IFLA_INFO_KIND', 'dummy']]})
        self.interface = self.ip.link_lookup(ifname='dummyX')[0]

    def teardown(self):
        self.ip.link('delete', index=self.interface)
        self.ip.release()


class TestIngress(BasicTest):

    def test_simple(self):
        self.ip.tc(RTM_NEWQDISC, 'ingress', self.interface, 0xffff0000)
        # get qdiscs list and filter out our interface
        qds = [x for x in self.ip.get_qdiscs() if
               x['index'] == self.interface]
        # assert the list is not empty
        assert qds
        # assert there is the ingress queue
        assert qds[0].get_attr('TCA_KIND') == ['ingress']

    def test_filter(self):
        self.test_simple()
        self.ip.tc(RTM_NEWTFILTER, 'u32', self.interface, 0,
                   protocol=socket.AF_INET,
                   parent=0xffff0000,
                   target=0x1,
                   rate='10kbit',
                   burst=10240,
                   limit=0,
                   prio=50,
                   keys=['0x0/0x0+12'])
        assert grep('tc filter show dev dummyX parent ffff:',
                    'rate 10000bit burst 10Kb')
