'''
A set of platform tests to discover the system capabilities
'''
import threading
from pyroute2.common import uifname
from pyroute2 import RawIPRoute


class TestCapsRtnl(object):

    def __init__(self):
        self.capabilities = {}
        self.ifnames = [uifname() for _ in range(10)]

    def __getitem__(self, key):
        return self.capabilities[key]

    def set_capability(self, key, value):
        self.capabilities[key] = value

    def setup(self):
        self.ip = RawIPRoute()

    def teardown(self):
        for ifname in self.ifnames:
            idx = self.ip.link_lookup(ifname=ifname)
            if idx:
                self.ip.link_remove(idx[0])
        self.ip.close()

    def collect(self):
        symbols = dir(self)
        for name in symbols:
            if name.startswith('test_'):
                self.setup()
                try:
                    ret = getattr(self, name)()
                    if ret is None:
                        ret = True
                    self.set_capability(name[5:], ret)
                except Exception:
                    self.set_capability(name[5:], False)
                self.teardown()

    def test_create_dummy(self):
        self.ip.link_create(ifname=self.ifnames[0], kind='dummy')

    def test_create_bridge(self):
        self.ip.link_create(ifname=self.ifnames[0], kind='bridge')

    def test_create_bond(self):
        self.ip.link_create(ifname=self.ifnames[0], kind='bond')

    def test_ghost_newlink(self):
        counters = {}
        # bouncer try
        #
        # if the kernel doesn't support dummy interfaces, the
        # test will fail immediately and will not start the
        # monitoring thread
        #
        # this RTM_NEWLINK is not counted
        self.ip.link_create(ifname=self.ifnames[0], kind='dummy')

        #
        # start monitoring thread
        def monitor(counters):
            ip = RawIPRoute()
            ip.bind()
            while counters.get('RTM_DELLINK', 0) < 2:
                msgs = ip.get()
                for msg in msgs:
                    if msg.get_attr('IFLA_IFNAME') != self.ifnames[0]:
                        # in an ideal case we should match indices
                        continue
                    if msg.get('event', None) in counters:
                        counters[msg.get('event', None)] += 1
                    else:
                        counters[msg.get('event', None)] = 1
            ip.close()
        t = threading.Thread(target=monitor, args=(counters, ))
        t.start()
        # 1st delete
        self.ip.link_remove(self.ip.link_lookup(ifname=self.ifnames[0]))
        # 2nd create + delete, loops exits
        self.ip.link_create(ifname=self.ifnames[0], kind='dummy')
        self.ip.link_remove(self.ip.link_lookup(ifname=self.ifnames[0]))
        # join the monitoring thread
        t.join()
        # assert counters
        #
        # normal flow:
        #   RTM_DELLINK: 2
        #   RTM_NEWLINK: 1
        #
        # the zombie case:
        #   RTM_DELLINK: 2
        #   RTM_NEWLINK: >= 2
        #
        # the cause is that when you delete an interface on old kernels,
        # you get first RTM_DELLINK and then one or more RTM_NEWLINK for
        # the same interface immediately
        #
        assert counters['RTM_NEWLINK'] > 1
        # return extra RTM_NEWLINK hits as the ghost counter
        return counters['RTM_NEWLINK']
