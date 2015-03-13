from pyroute2.ipset import IPSet
from pyroute2.netlink import NetlinkError
from utils import require_user
from uuid import uuid4


class TestIPSet(object):

    def setup(self):
        self.ip = IPSet()

    def teardown(self):
        self.ip.close()

    def list_ipset(self, name):
        try:
            return [x.get_attr('IPSET_ATTR_IP_FROM').
                    get_attr('IPSET_ATTR_IPADDR_IPV4')
                    for x in
                    self.ip.list(name)[0].
                    get_attr('IPSET_ATTR_ADT').
                    get_attrs('IPSET_ATTR_PROTO')]
        except:
            return []

    def get_ipset(self, name):
        return [x for x in self.ip.list()
                if x.get_attr('IPSET_ATTR_SETNAME') == name]

    def test_create_exclusive_fail(self):
        require_user('root')
        name = str(uuid4())[:16]
        self.ip.create(name)
        assert self.get_ipset(name)
        try:
            self.ip.create(name)
        except NetlinkError as e:
            if e.code != 17:  # File exists
                raise
        finally:
            self.ip.destroy(name)
        assert not self.get_ipset(name)

    def test_create_exclusive_success(self):
        require_user('root')
        name = str(uuid4())[:16]
        self.ip.create(name)
        assert self.get_ipset(name)
        self.ip.create(name, exclusive=False)
        self.ip.destroy(name)
        assert not self.get_ipset(name)

    def test_add_exclusive_fail(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        self.ip.create(name)
        self.ip.add(name, ipaddr)
        assert ipaddr in self.list_ipset(name)
        try:
            self.ip.add(name, ipaddr)
        except NetlinkError:
            pass
        finally:
            self.ip.destroy(name)
        assert not self.get_ipset(name)

    def test_add_exclusive_success(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        self.ip.create(name)
        self.ip.add(name, ipaddr)
        assert ipaddr in self.list_ipset(name)
        self.ip.add(name, ipaddr, exclusive=False)
        self.ip.destroy(name)
        assert not self.get_ipset(name)

    def test_create_destroy(self):
        require_user('root')
        name = str(uuid4())[:16]
        # create ipset
        self.ip.create(name)
        # assert it exists
        assert self.get_ipset(name)
        # remove ipset
        self.ip.destroy(name)
        # assert it is removed
        assert not self.get_ipset(name)

    def test_add_delete(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '192.168.1.1'
        # create ipset
        self.ip.create(name)
        assert self.get_ipset(name)
        # add an entry
        self.ip.add(name, ipaddr)
        # check it
        assert ipaddr in self.list_ipset(name)
        # delete an entry
        self.ip.delete(name, ipaddr)
        # check it
        assert ipaddr not in self.list_ipset(name)
        # remove ipset
        self.ip.destroy(name)
        assert not self.get_ipset(name)

    def test_swap(self):
        require_user('root')
        name_a = str(uuid4())[:16]
        name_b = str(uuid4())[:16]
        ipaddr_a = '192.168.1.1'
        ipaddr_b = '10.0.0.1'

        # create sets
        self.ip.create(name_a)
        self.ip.create(name_b)
        # add ips
        self.ip.add(name_a, ipaddr_a)
        self.ip.add(name_b, ipaddr_b)
        assert ipaddr_a in self.list_ipset(name_a)
        assert ipaddr_b in self.list_ipset(name_b)
        # swap sets
        self.ip.swap(name_a, name_b)
        assert ipaddr_a in self.list_ipset(name_b)
        assert ipaddr_b in self.list_ipset(name_a)
        # remove sets
        self.ip.destroy(name_a)
        self.ip.destroy(name_b)
        assert not self.get_ipset(name_a)
        assert not self.get_ipset(name_b)
