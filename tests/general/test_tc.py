import socket
from utils import require_user
from utils import get_simple_bpf_program
from utils import skip_if_not_supported
from pyroute2 import IPRoute
from pyroute2 import protocols
from pyroute2.common import uifname
from pyroute2.netlink.rtnl import TC_H_INGRESS
from nose.plugins.skip import SkipTest


class BasicTest(object):

    def setup(self):
        require_user('root')
        self.ip = IPRoute()
        self.ifname = uifname()
        self.ip.link_create(ifname=self.ifname, kind='dummy')
        self.interface = self.ip.link_lookup(ifname=self.ifname)[0]

    def teardown(self):
        self.ip.link('delete', index=self.interface)
        self.ip.close()

    def get_qdiscs(self):
        return [x for x in self.ip.get_qdiscs() if
                x['index'] == self.interface]

    def get_qdisc(self):
        # get qdiscs list and filter out our interface
        qds = self.get_qdiscs()
        if qds:
            return qds[0]
        else:
            return None


class TestIngress(BasicTest):

    def test_simple(self):
        self.ip.tc('add', 'ingress', self.interface, 0xffff0000)
        qds = self.get_qdisc()
        # assert the list is not empty
        assert qds
        # assert there is the ingress queue
        assert qds.get_attr('TCA_KIND') == 'ingress'
        # assert it has proper handle and parent
        assert qds['handle'] == 0xffff0000
        assert qds['parent'] == TC_H_INGRESS

    def test_filter(self):
        self.test_simple()
        self.ip.tc('add-filter', 'u32', self.interface, 0,
                   protocol=socket.AF_INET,
                   parent=0xffff0000,
                   action='drop',
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
               (x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_POLICE')
                is not None or
                x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_ACT')
                is not None)][0]
        # assert the police rule has specified parameters
        options = prs.get_attr('TCA_OPTIONS')
        police_u32 = options.get_attr('TCA_U32_POLICE')
        # on modern kernels there is no TCA_U32_POLICE under
        # TCA_OPTIONS, but there is TCA_U32_ACT
        if police_u32 is None:
            police_u32 = options.get_attr('TCA_U32_ACT').\
                get_attr('TCA_ACT_PRIO_0').\
                get_attr('TCA_ACT_OPTIONS')
        police_tbf = police_u32.get_attr('TCA_POLICE_TBF')
        assert police_tbf['rate'] == 1250
        assert police_tbf['mtu'] == 2040

    @skip_if_not_supported
    def test_bpf_filter(self):
        self.test_simple()
        fd1 = get_simple_bpf_program('sched_cls')
        fd2 = get_simple_bpf_program('sched_act')
        if fd1 == -1 or fd2 == -1:
            # to get bpf filter working, one should have:
            # kernel >= 4.1
            # CONFIG_EXPERT=y
            # CONFIG_BPF_SYSCALL=y
            # CONFIG_NET_CLS_BPF=m/y
            #
            # see `grep -rn BPF_PROG_TYPE_SCHED_CLS kernel_sources`
            raise SkipTest('bpf syscall error')
        self.ip.tc('add-filter', 'bpf', self.interface, 0,
                   fd=fd1, name='my_func', parent=0xffff0000,
                   action='ok', classid=1)
        action = {'kind': 'bpf', 'fd': fd2, 'name': 'my_func', 'action': 'ok'}
        self.ip.tc('add-filter', 'u32', self.interface, 1,
                   protocol=protocols.ETH_P_ALL, parent=0xffff0000,
                   target=0x10002, keys=['0x0/0x0+0'], action=action)
        fls = self.ip.get_filters(index=self.interface, parent=0xffff0000)
        assert fls
        bpf_filter = [x for x in fls
                      if x.get_attr('TCA_OPTIONS') is not None and
                      (x.get_attr('TCA_OPTIONS').get_attr('TCA_BPF_ACT')
                       is not None)][0]
        bpf_options = bpf_filter.get_attr('TCA_OPTIONS')
        gact_parms = bpf_options.get_attr('TCA_BPF_ACT').\
            get_attr('TCA_ACT_PRIO_1').\
            get_attr('TCA_ACT_OPTIONS').\
            get_attr('TCA_GACT_PARMS')
        assert gact_parms['action'] == 0

        u32_filter = [x for x in fls
                      if x.get_attr('TCA_OPTIONS') is not None and
                      (x.get_attr('TCA_OPTIONS').get_attr('TCA_U32_ACT')
                       is not None)][0]
        u32_options = u32_filter.get_attr('TCA_OPTIONS')
        bpf_fd = u32_options.get_attr('TCA_U32_ACT').\
            get_attr('TCA_ACT_PRIO_1').\
            get_attr('TCA_ACT_OPTIONS').\
            get_attr('TCA_ACT_BPF_FD')
        assert bpf_fd == fd2

    @skip_if_not_supported
    def test_bpf_filter_policer(self):
        self.test_simple()
        fd = get_simple_bpf_program('sched_cls')
        if fd == -1:
            # see comment above about kernel requirements
            raise SkipTest('bpf syscall error')
        self.ip.tc('add-filter', 'bpf', self.interface, 0,
                   fd=fd, name='my_func', parent=0xffff0000,
                   action='ok', classid=1, rate='10kbit',
                   burst=10240, mtu=2040)
        fls = self.ip.get_filters(index=self.interface, parent=0xffff0000)
        # assert the supplied policer is returned to us intact
        plcs = [x for x in fls
                if x.get_attr('TCA_OPTIONS') is not None and
                (x.get_attr('TCA_OPTIONS').get_attr('TCA_BPF_POLICE')
                 is not None)][0]
        options = plcs.get_attr('TCA_OPTIONS')
        police = options.get_attr('TCA_BPF_POLICE').\
            get_attr('TCA_POLICE_TBF')
        assert police['rate'] == 1250
        assert police['mtu'] == 2040


class TestSimpleQueues(BasicTest):

    def test_pfifo(self):
        self.ip.tc('add', 'pfifo_fast', self.interface, 0)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'pfifo_fast'
        assert isinstance(qds.get_attr('TCA_OPTIONS')['priomap'], tuple)

    @skip_if_not_supported
    def test_plug(self):
        self.ip.tc('add', 'plug', self.interface, limit=13107)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'plug'

    @skip_if_not_supported
    def test_blackhole(self):
        self.ip.tc('add', 'blackhole', self.interface)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'blackhole'

    @skip_if_not_supported
    def test_codel(self):
        self.ip.tc('add', 'codel', self.interface,
                   handle='1:0',
                   cdl_interval='40ms',
                   cdl_target='2ms',
                   cdl_limit=5000,
                   cdl_ecn=1)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'codel'
        opts = qds.get_attr('TCA_OPTIONS')
        assert opts.get_attr('TCA_CODEL_ECN') == 1
        assert opts.get_attr('TCA_CODEL_LIMIT') == 5000

    @skip_if_not_supported
    def test_sfq(self):
        self.ip.tc('add', 'sfq', self.interface, 0, perturb=10)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'sfq'
        assert qds.get_attr('TCA_OPTIONS')['perturb_period'] == 10

    @skip_if_not_supported
    def test_tbf(self):
        self.ip.tc('add', 'tbf', self.interface, 0,
                   rate='220kbit',
                   latency='50ms',
                   burst=1540)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'tbf'
        opts = qds.get_attr('TCA_OPTIONS').get_attr('TCA_TBF_PARMS')
        assert opts
        assert opts['rate'] == 27500

    @skip_if_not_supported
    def test_choke(self):
        self.ip.tc('add', 'choke', self.interface,
                   limit=5500,
                   bandwith=3000,
                   ecn=True)
        qds = self.get_qdisc()
        assert qds.get_attr('TCA_KIND') == 'choke'
        opts = qds.get_attr('TCA_OPTIONS').get_attr('TCA_CHOKE_PARMS')
        assert opts['limit'] == 5500
        assert opts['qth_max'] == 1375
        assert opts['qth_min'] == 458


class TestHfsc(BasicTest):

    @skip_if_not_supported
    def test_hfsc(self):
        # root queue
        self.ip.tc('add', 'hfsc', self.interface,
                   handle='1:0',
                   default='1:1')
        qds = self.get_qdiscs()
        assert len(qds) == 1
        assert qds[0].get_attr('TCA_KIND') == 'hfsc'
        assert qds[0].get_attr('TCA_OPTIONS')['defcls'] == 1
        # classes
        self.ip.tc('add-class', 'hfsc', self.interface,
                   handle='1:1',
                   parent='1:0',
                   rsc={'m2': '3mbit'})
        cls = self.ip.get_classes(index=self.interface)
        assert len(cls) == 2  # implicit root class + the defined one
        assert cls[0].get_attr('TCA_KIND') == 'hfsc'
        assert cls[1].get_attr('TCA_KIND') == 'hfsc'
        curve = cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_RSC')
        assert curve['m1'] == 0
        assert curve['d'] == 0
        assert curve['m2'] == 375000
        assert cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_FSC') is None
        assert cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_USC') is None


class TestHtb(BasicTest):

    @skip_if_not_supported
    def test_htb(self):
        # 8<-----------------------------------------------------
        # root queue, '1:0' handle notation
        self.ip.tc('add', 'htb', self.interface, '1:', default='20:0')

        qds = self.get_qdiscs()
        assert len(qds) == 1
        assert qds[0].get_attr('TCA_KIND') == 'htb'

        # 8<-----------------------------------------------------
        # classes, both string and int handle notation
        self.ip.tc('add-class', 'htb', self.interface, '1:1',
                   parent='1:0',
                   rate='256kbit',
                   burst=1024 * 6)
        self.ip.tc('add-class', 'htb', self.interface, 0x10010,
                   parent=0x10001,
                   rate='192kbit',
                   burst=1024 * 6,
                   prio=1)
        self.ip.tc('add-class', 'htb', self.interface, '1:20',
                   parent='1:1',
                   rate='128kbit',
                   burst=1024 * 6,
                   prio=2)
        cls = self.ip.get_classes(index=self.interface)
        assert len(cls) == 3

        # 8<-----------------------------------------------------
        # leaves, both string and int handle notation
        self.ip.tc('add', 'sfq', self.interface, '10:',
                   parent='1:10',
                   perturb=10)
        self.ip.tc('add', 'sfq', self.interface, 0x200000,
                   parent=0x10020,
                   perturb=10)
        qds = self.get_qdiscs()
        types = set([x.get_attr('TCA_KIND') for x in qds])
        assert types == set(('htb', 'sfq'))

        # 8<-----------------------------------------------------
        # filters, both string and int handle notation
        #
        # Please note, that u32 filter requires ethernet protocol
        # numbers, as defined in protocols module. Do not provide
        # here socket.AF_INET and so on.
        #
        self.ip.tc('add-filter', 'u32', self.interface, '0:0',
                   parent='1:0',
                   prio=10,
                   protocol=protocols.ETH_P_IP,
                   target='1:10',
                   keys=['0x0006/0x00ff+8', '0x0000/0xffc0+2'])
        self.ip.tc('add-filter', 'u32', self.interface, 0,
                   parent=0x10000,
                   prio=10,
                   protocol=protocols.ETH_P_IP,
                   target=0x10020,
                   keys=['0x5/0xf+0', '0x10/0xff+33'])
        # 2 filters + 2 autogenerated
        fls = self.ip.get_filters(index=self.interface)
        assert len(fls) == 4

    @skip_if_not_supported
    def test_replace(self):
        self.test_htb()
        # change class
        self.ip.tc('replace-class', 'htb', self.interface,
                   handle=0x10010, parent=0x10001,
                   rate='102kbit',
                   burst=1024 * 6,
                   prio=3)
        clss = self.ip.get_classes(index=self.interface)
        for cls in clss:
            if cls['handle'] == 0x10010:
                break
        else:
            raise Exception('target class not found')
        opts = cls.get_attr('TCA_OPTIONS')
        params = opts.get_attr('TCA_HTB_PARMS')

        assert params['prio'] == 3
        assert params['quantum'] * 8 == 10200
