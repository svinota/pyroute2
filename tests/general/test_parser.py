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


class TestRtnl(TestNL):

    marshal = MarshalRtnl

    def test_addrmsg_ipv4(self):
        pkts, _ = self.parse('data/addrmsg_ipv4')

        # one can use either approach for messages testing:
        # asserts of particular fields / attrs, or compare
        # the decoded message with some prime (see below)
        assert len(pkts) == 1
        assert len(pkts[0]['attrs']) == 5
        assert pkts[0]['event'] == 'RTM_NEWADDR'
        assert pkts[0].get_attr('IFA_ADDRESS') == '127.0.0.1'
        assert pkts[0].get_attr('IFA_LOCAL') == '127.0.0.1'
        assert pkts[0].get_attr('IFA_LABEL') == 'lo'
        assert pkts[0].get_attr('IFA_CACHEINFO')['ifa_prefered'] == 0xffffffff

    def test_gre(self):
        pkts, _ = self.parse('data/gre_01')
        assert len(pkts) == 2
        value = {'attrs': [['IFLA_IFNAME', 'mgre0'],
                           ['IFLA_LINKINFO',
                            {'attrs': [['IFLA_INFO_KIND', 'gre'],
                                       ['IFLA_INFO_DATA',
                                        {'attrs': [['IFLA_GRE_IKEY', 0],
                                                   ['IFLA_GRE_OKEY', 0],
                                                   ['IFLA_GRE_IFLAGS', 0],
                                                   ['IFLA_GRE_OFLAGS', 0],
                                                   ['IFLA_GRE_LOCAL',
                                                    '192.168.122.1'],
                                                   ['IFLA_GRE_REMOTE',
                                                    '192.168.122.60'],
                                                   ['IFLA_GRE_PMTUDISC', 1],
                                                   ['IFLA_GRE_TTL', 16],
                                                   ['IFLA_GRE_TOS', 0]]}]]}]],
                 'change': 0,
                 'event': 'RTM_NEWLINK',
                 'family': 0,
                 'flags': 0,
                 'header': {'error': None,
                            'flags': 1541,
                            'length': 132,
                            'pid': 0,
                            'sequence_number': 1426284873,
                            'type': 16},
                 'ifi_type': 0,
                 'index': 0}

        # instantiate the message object using class from decoded packet
        prime = type(pkts[0])()
        # set the message value; it is only value -- the buffer stays
        # empty
        prime.setvalue(value)
        # compare that the decoded message matches what we expect from it
        assert pkts[0] == prime


class TestNl80211(TestNL):

    marshal = MarshalNl80211

    def test_iw_info(self):
        pkts, _ = self.parse('data/iw_info_rsp')
        assert len(pkts) == 1
        value = {'attrs': [['NL80211_ATTR_IFINDEX', 3],
                           ['NL80211_ATTR_IFNAME', 'wlo1'],
                           ['NL80211_ATTR_WIPHY', 0],
                           ['NL80211_ATTR_IFTYPE', 2],
                           ['NL80211_ATTR_WDEV', 1],
                           ['NL80211_ATTR_MAC', 'a4:4e:31:43:1c:7d'],
                           ['NL80211_ATTR_GENERATION', 5]],
                 'cmd': 7,
                 'event': 'NL80211_CMD_NEW_INTERFACE',
                 'header': {'error': None,
                            'flags': 0,
                            'length': 88,
                            'pid': 771783666,
                            'sequence_number': 1423833650,
                            'type': 27},
                 'reserved': 0,
                 'version': 1}

        prime = type(pkts[0])()
        prime.setvalue(value)
        assert prime == pkts[0]

    def test_iw_scan(self):
        pkts, values = self.parse('data/iw_scan_rsp')
        assert len(pkts) == len(values) == 4

        for idx in range(len(pkts)):
            prime = type(pkts[idx])()
            prime.setvalue(values[idx])
            assert prime == pkts[idx]
