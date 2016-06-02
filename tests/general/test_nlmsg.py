from pyroute2.common import load_dump
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.netlink.nl80211 import MarshalNl80211


prime = {'attrs': (('A', 2),
                   ('A', 3),
                   ('A', 4),
                   ('B', {'attrs': (('C', 5),
                                    ('D', {'attrs': (('E', 6),
                                                     ('F', 7))}))}))}


class TestAttrs(object):

    def setup(self):
        self.msg = nlmsg()
        self.msg.setvalue(prime)

    def test_get_attr(self):
        assert self.msg.get_attr('A') == 2
        assert self.msg.get_attr('C') is None

    def test_get_attrs(self):
        assert self.msg.get_attrs('A') == [2, 3, 4]
        assert self.msg.get_attrs('C') == []

    def test_get_nested(self):
        assert self.msg.get_nested('B', 'D', 'E') == 6
        assert self.msg.get_nested('B', 'D', 'F') == 7
        assert self.msg.get_nested('B', 'D', 'G') is None
        assert self.msg.get_nested('C', 'D', 'E') is None


class TestNL(object):

    marshal = None

    def parse(self, fname):
        with open(fname, 'r') as f:
            m = self.marshal()
            meta = {}
            code = None
            d = load_dump(f, meta)
            pkts = m.parse(d)
            if meta.get('code'):
                code = eval(meta['code'])
            return pkts, code

    def load_data(self, fname, packets=1):
        pkts, values = self.parse(fname)
        if not isinstance(values, (list, tuple)):
            values = [values]
        assert len(pkts) == len(values) == packets
        for idx in range(len(pkts)):
            prime = type(pkts[idx])()
            prime.setvalue(values[idx])
            assert prime == pkts[idx]


class TestRtnl(TestNL):

    marshal = MarshalRtnl

    def test_addrmsg_ipv4(self):
        self.load_data(fname='decoder/addrmsg_ipv4', packets=1)

    def test_gre(self):
        self.load_data(fname='decoder/gre_01', packets=2)


class TestNl80211(TestNL):

    marshal = MarshalNl80211

    def test_iw_info(self):
        self.load_data(fname='decoder/iw_info_rsp', packets=1)

    def _test_iw_scan(self):
        self.load_data(fname='decoder/iw_scan_rsp', packets=4)
