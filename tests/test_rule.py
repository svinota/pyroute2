from utils import require_user
from pyroute2 import IPRoute


class TestRule(object):

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
        self.ip.close()

    def test_basic(self):
        self.ip.rule('add', 10, 32000)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32000 and
                    x.get_attr('FRA_TABLE') == 10]) == 1
        self.ip.rule('delete', 10, 32000)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32000 and
                    x.get_attr('FRA_TABLE') == 10]) == 0

    def test_fwmark(self):
        self.ip.rule('add', 15, 32006, fwmark=10)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32006 and
                    x.get_attr('FRA_TABLE') == 15 and
                    x.get_attr('FRA_FWMARK')]) == 1
        self.ip.rule('delete', 15, 32006, fwmark=10)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32006 and
                    x.get_attr('FRA_TABLE') == 15 and
                    x.get_attr('FRA_FWMARK')]) == 0

    def test_bad_table(self):
        try:
            self.ip.rule('add', -1, 32000)
        except ValueError:
            pass

    def test_big_table(self):
        self.ip.rule('add', 1024, 32000)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32000 and
                    x.get_attr('FRA_TABLE') == 1024]) == 1
        self.ip.rule('delete', 1024, 32000)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32000 and
                    x.get_attr('FRA_TABLE') == 1024]) == 0

    def test_src_dst(self):
        self.ip.rule('add', 17, 32005,
                     src='10.0.0.0', src_len=24,
                     dst='10.1.0.0', dst_len=24)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32005 and
                    x.get_attr('FRA_TABLE') == 17 and
                    x.get_attr('FRA_SRC') == '10.0.0.0' and
                    x.get_attr('FRA_DST') == '10.1.0.0' and
                    x['src_len'] == 24 and
                    x['dst_len'] == 24]) == 1
        self.ip.rule('delete', 17, 32005,
                     src='10.0.0.0', src_len=24,
                     dst='10.1.0.0', dst_len=24)
        assert len([x for x in self.ip.get_rules() if
                    x.get_attr('FRA_PRIORITY') == 32005 and
                    x.get_attr('FRA_TABLE') == 17 and
                    x.get_attr('FRA_SRC') == '10.0.0.0' and
                    x.get_attr('FRA_DST') == '10.1.0.0' and
                    x['src_len'] == 24 and
                    x['dst_len'] == 24]) == 0
