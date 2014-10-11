import socket
from pyroute2 import IPRoute
from pyroute2.netlink import NetlinkError
from utils import grep
from utils import require_user
from utils import get_ip_addr
from utils import get_ip_link
from utils import get_ip_route
from utils import get_ip_default_routes
from utils import get_ip_rules
from utils import create_link
from utils import remove_link


class TestSetup(object):

    def test_simple(self):
        ip = IPRoute()
        ip.close()

    def test_multiple_instances(self):
        # run two instances from parent
        # and two instances from child
        ip1 = IPRoute()
        ip2 = IPRoute()
        # `fork` is DEPRECATED
        ip3 = IPRoute(fork=True)
        ip4 = IPRoute(fork=True)
        ip1.close()
        ip2.close()
        ip3.close()
        ip4.close()


class TestMisc(object):

    def setup(self):
        self.ip = IPRoute()

    def teardown(self):
        self.ip.close()

    def test_addrpool_expand(self):
        # see coverage
        for i in range(100):
            self.ip.get_addr()

    def test_nla_compare(self):
        lvalue = self.ip.get_links()
        rvalue = self.ip.get_links()
        assert lvalue is not rvalue
        if lvalue == rvalue:
            pass
        if lvalue != rvalue:
            pass
        assert lvalue != 42


def _callback(msg, obj):
    obj.cb_counter += 1


class TestData(object):

    def setup(self):
        create_link('dummyX', 'dummy')
        self.ip = IPRoute()
        self.dev = self.ip.link_lookup(ifname='dummyX')

    def teardown(self):
        self.ip.close()
        remove_link('dummyX')
        remove_link('bala')

    def _test_nla_operators(self):
        require_user('root')
        dev = self.dev[0]
        self.ip.addr('add', dev, address='172.16.0.1', mask=24)
        self.ip.addr('add', dev, address='172.16.0.2', mask=24)
        r = [x for x in self.ip.get_addr() if x['index'] == dev]
        complement = r[0] - r[1]
        intersection = r[0] & r[1]

        assert complement.get_attr('IFA_ADDRESS') == '172.16.0.1'
        assert complement.get_attr('IFA_LABEL') is None
        assert complement['prefixlen'] == 0
        assert complement['index'] == 0

        assert intersection.get_attr('IFA_ADDRESS') is None
        assert intersection.get_attr('IFA_LABEL') == 'dummyX'
        assert intersection['prefixlen'] == 24
        assert intersection['index'] == dev

    def test_add_addr(self):
        require_user('root')
        dev = self.dev[0]
        self.ip.addr('add', dev, address='172.16.0.1', mask=24)
        assert '172.16.0.1/24' in get_ip_addr()

    def test_fail_not_permitted(self):
        try:
            self.ip.addr('add', 1, address='172.16.0.1', mask=24)
        except NetlinkError as e:
            if e.code != 1:  # Operation not permitted
                raise
        finally:
            try:
                self.ip.addr('delete', 1, address='172.16.0.1', mask=24)
            except:
                pass

    def test_fail_no_such_device(self):
        require_user('root')
        dev = sorted([i['index'] for i in self.ip.get_links()])[-1] + 10
        try:
            self.ip.addr('add',
                         dev,
                         address='172.16.0.1',
                         mask=24)
        except NetlinkError as e:
            if e.code != 19:  # No such device
                raise

    def test_remove_link(self):
        require_user('root')
        create_link('bala', 'dummy')
        dev = self.ip.link_lookup(ifname='bala')[0]
        try:
            self.ip.link_remove(dev)
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 0

    def test_get_route(self):
        if not self.ip.get_default_routes(table=254):
            return
        rts = self.ip.get_routes(family=socket.AF_INET,
                                 dst='8.8.8.8',
                                 table=254)
        assert len(rts) > 0

    def test_flush_routes(self):
        require_user('root')
        create_link('bala', 'dummy')
        dev = self.ip.link_lookup(ifname='bala')[0]
        self.ip.link('set', index=dev, state='up')
        self.ip.addr('add', dev, address='172.16.0.2', mask=24)
        self.ip.route('add',
                      prefix='172.16.1.0',
                      mask=24,
                      gateway='172.16.0.1',
                      table=100)
        self.ip.route('add',
                      prefix='172.16.2.0',
                      mask=24,
                      gateway='172.16.0.1',
                      table=100)

        assert grep('ip route show table 100',
                    pattern='172.16.1.0/24.*172.16.0.1')
        assert grep('ip route show table 100',
                    pattern='172.16.2.0/24.*172.16.0.1')

        self.ip.flush_routes(table=100)

        assert not grep('ip route show table 100',
                        pattern='172.16.1.0/24.*172.16.0.1')
        assert not grep('ip route show table 100',
                        pattern='172.16.2.0/24.*172.16.0.1')

        remove_link('bala')

    def test_route_table_2048(self):
        require_user('root')
        create_link('bala', 'dummy')
        dev = self.ip.link_lookup(ifname='bala')[0]
        self.ip.link('set', index=dev, state='up')
        self.ip.addr('add', dev, address='172.16.0.2', mask=24)
        self.ip.route('add',
                      prefix='172.16.1.0',
                      mask=24,
                      gateway='172.16.0.1',
                      table=2048)
        assert grep('ip route show table 2048',
                    pattern='172.16.1.0/24.*172.16.0.1')
        remove_link('bala')

    def test_symbolic_flags(self):
        require_user('root')
        dev = self.dev[0]
        self.ip.link('set', index=dev, flags=['IFF_UP'])
        assert self.ip.get_links(dev)[0]['flags'] & 1
        self.ip.link('set', index=dev, flags=['!IFF_UP'])
        assert not (self.ip.get_links(dev)[0]['flags'] & 1)

    def test_updown_link(self):
        require_user('root')
        dev = self.dev[0]
        assert not (self.ip.get_links(dev)[0]['flags'] & 1)
        try:
            self.ip.link_up(dev)
        except NetlinkError:
            pass
        assert self.ip.get_links(dev)[0]['flags'] & 1
        try:
            self.ip.link_down(dev)
        except NetlinkError:
            pass
        assert not (self.ip.get_links(dev)[0]['flags'] & 1)

    def test_callbacks_positive(self):
        require_user('root')
        dev = self.dev[0]

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == dev,
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter > 0
        self.ip.unregister_callback(_callback)

    def test_callbacks_negative(self):
        require_user('root')

        self.cb_counter = 0
        self.ip.register_callback(_callback,
                                  lambda x: x.get('index', None) == 'bala',
                                  (self, ))
        self.test_updown_link()
        assert self.cb_counter == 0
        self.ip.unregister_callback(_callback)

    def test_rename_link(self):
        require_user('root')
        dev = self.dev[0]
        try:
            self.ip.link_rename(dev, 'bala')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='bala')) == 1
        try:
            self.ip.link_rename(dev, 'dummyX')
        except NetlinkError:
            pass
        assert len(self.ip.link_lookup(ifname='dummyX')) == 1

    def test_rules(self):
        assert len(get_ip_rules('-4')) == \
            len(self.ip.get_rules(socket.AF_INET))
        assert len(get_ip_rules('-6')) == \
            len(self.ip.get_rules(socket.AF_INET6))

    def test_addr(self):
        assert len(get_ip_addr()) == len(self.ip.get_addr())

    def test_links(self):
        assert len(get_ip_link()) == len(self.ip.get_links())

    def test_one_link(self):
        lo = self.ip.get_links(1)[0]
        assert lo.get_attr('IFLA_IFNAME') == 'lo'

    def test_default_routes(self):
        assert len(get_ip_default_routes()) == \
            len(self.ip.get_default_routes(family=socket.AF_INET, table=254))

    def test_routes(self):
        assert len(get_ip_route()) == \
            len(self.ip.get_routes(family=socket.AF_INET, table=255))
