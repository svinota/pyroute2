from pyroute2.common import load_dump
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.netlink.nl80211 import MarshalNl80211


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


class _TestRtnl(TestNL):

    marshal = MarshalRtnl

    def test_addrmsg_ipv4(self):
        self.load_data(fname='decoder/addrmsg_ipv4', packets=1)

    def test_gre(self):
        self.load_data(fname='decoder/gre_01', packets=2)


class _TestNl80211(TestNL):

    marshal = MarshalNl80211

    def test_iw_info(self):
        self.load_data(fname='decoder/iw_info_rsp', packets=1)

    def test_iw_scan(self):
        self.load_data(fname='decoder/iw_scan_rsp', packets=4)
