from pyroute2.ipset import IPSet
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
