import socket
from utils import require_user
from pyroute2 import IPRoute
from pyroute2.netlink.iproute import RTM_NEWQDISC
from pyroute2.netlink.iproute import RTM_NEWTFILTER
from pyroute2.netlink.iproute import TC_H_INGRESS


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
        qds = [x for x in self.ip.get_qdiscs() if x['index'] == self.interface]
        # assert the list is not empty
        assert qds
        # assert there is the ingress queue
        assert qds[0].get_attr('TCA_KIND') == 'ingress'
        # assert it has proper handle and parent
        assert qds[0]['handle'] == 0xffff0000
        assert qds[0]['parent'] == TC_H_INGRESS

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
        fls = self.ip.get_filters(index=self.interface, parent=0xffff0000)
        # assert there are filters
        assert fls
        # assert there is one police rule:
        prs = [x for x in fls
               if x.get_attr('TCA_OPTIONS') is not None and
               x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_POLICE')
               is not None][0]
        # assert the police rule has specified parameters
        options = prs.get_attr('TCA_OPTIONS')
        police_u32 = options.get_attr('TCA_U32_POLICE')
        police_tbf = police_u32.get_attr('TCA_POLICE_TBF')
        assert police_tbf['rate'] == 1250
        assert police_tbf['mtu'] == 2040


class TestSfq(BasicTest):

    def test_sfq(self):
        self.ip.tc(RTM_NEWQDISC, 'sfq', self.interface, 0, perturb=10)
        qds = [x for x in self.ip.get_qdiscs() if x['index'] == self.interface]
        if qds:
            qds = qds[0]
        assert qds
        assert qds.get_attr('TCA_KIND') == 'sfq'
        assert qds.get_attr('TCA_OPTIONS')['perturb_period'] == 10
