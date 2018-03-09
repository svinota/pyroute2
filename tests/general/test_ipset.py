import errno
from time import sleep
from pyroute2.ipset import IPSet, PortRange, PortEntry
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.nfnetlink.ipset import IPSET_FLAG_WITH_FORCEADD
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_TYPE_SPECIFIC
from utils import require_user
from uuid import uuid4

import socket


class TestIPSet(object):

    def setup(self):
        self.ip = IPSet()

    def teardown(self):
        self.ip.close()

    @staticmethod
    def parse_ip(entry):
        ip_from = entry.get_attr('IPSET_ATTR_IP_FROM')
        return ip_from.get_attr('IPSET_ATTR_IPADDR_IPV4')

    def parse_net(self, entry):
        net = self.parse_ip(entry)
        cidr = entry.get_attr("IPSET_ATTR_CIDR")
        if cidr is not None:
            net += '/{0}'.format(cidr)
        return net

    @staticmethod
    def ipset_type_to_entry_type(ipset_type):
        return ipset_type.split(':', 1)[1].split(',')

    def list_ipset(self, name):
        try:
            res = {}
            msg_list = self.ip.list(name)
            adt = 'IPSET_ATTR_ADT'
            proto = 'IPSET_ATTR_DATA'
            stype = 'IPSET_ATTR_TYPENAME'
            for msg in msg_list:
                for x in msg.get_attr(adt).get_attrs(proto):
                    entry = ''
                    msg_stypes = msg.get_attr(stype)
                    if msg_stypes is None:
                        msg_stypes = 'hash:ip'
                    for st in self.ipset_type_to_entry_type(msg_stypes):
                        if st == "ip":
                            entry = self.parse_ip(x)
                        elif st == "net":
                            entry = self.parse_net(x)
                        elif st == 'iface':
                            entry += x.get_attr('IPSET_ATTR_IFACE')
                        elif st == 'set':
                            entry += x.get_attr("IPSET_ATTR_NAME")
                        entry += ","

                    entry = entry.strip(",")

                    res[entry] = (x.get_attr("IPSET_ATTR_PACKETS"),
                                  x.get_attr("IPSET_ATTR_BYTES"),
                                  x.get_attr("IPSET_ATTR_COMMENT"),
                                  x.get_attr("IPSET_ATTR_TIMEOUT"),
                                  x.get_attr("IPSET_ATTR_SKBMARK"),
                                  x.get_attr("IPSET_ATTR_SKBPRIO"),
                                  x.get_attr("IPSET_ATTR_SKBQUEUE"))
            return res
        except:
            return {}

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
            if e.code != errno.EEXIST:  # File exists
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

    def test_counters(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        self.ip.create(name, counters=True)
        self.ip.add(name, ipaddr)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][0] == 0  # Bytes
        assert self.list_ipset(name)[ipaddr][1] == 0  # Packets
        self.ip.destroy(name)

        self.ip.create(name, counters=False)
        self.ip.add(name, ipaddr)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][0] is None
        assert self.list_ipset(name)[ipaddr][1] is None
        self.ip.destroy(name)

    def test_comments(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        comment = 'a very simple comment'
        self.ip.create(name, comment=True)
        self.ip.add(name, ipaddr, comment=comment)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][2] == comment
        self.ip.destroy(name)

    def test_skbmark(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        skbmark = (0x100, 0xffffffff)
        self.ip.create(name, skbinfo=True)
        self.ip.add(name, ipaddr, skbmark=skbmark)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][4] == skbmark
        self.ip.destroy(name)

    def test_skbprio(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        skbprio = (1, 10)
        self.ip.create(name, skbinfo=True)
        self.ip.add(name, ipaddr, skbprio=skbprio)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][5] == skbprio
        self.ip.destroy(name)

    def test_skbqueue(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipaddr = '172.16.202.202'
        skbqueue = 1
        self.ip.create(name, skbinfo=True)
        self.ip.add(name, ipaddr, skbqueue=skbqueue)
        assert ipaddr in self.list_ipset(name)
        assert self.list_ipset(name)[ipaddr][6] == skbqueue
        self.ip.destroy(name)

    def test_maxelem(self):
        require_user('root')
        name = str(uuid4())[:16]
        self.ip.create(name, maxelem=1)
        data = self.get_ipset(name)[0].get_attr("IPSET_ATTR_DATA")
        maxelem = data.get_attr("IPSET_ATTR_MAXELEM")
        self.ip.destroy(name)
        assert maxelem == 1

    def test_hashsize(self):
        require_user('root')
        name = str(uuid4())[:16]
        min_size = 64
        self.ip.create(name, hashsize=min_size)
        data = self.get_ipset(name)[0].get_attr("IPSET_ATTR_DATA")
        hashsize = data.get_attr("IPSET_ATTR_HASHSIZE")
        self.ip.destroy(name)
        assert hashsize == min_size

    def test_forceadd(self):
        require_user('root')
        name = str(uuid4())[:16]
        self.ip.create(name, forceadd=True)
        res = self.ip.list(name)[0].get_attr("IPSET_ATTR_DATA")

        flags = res.get_attr("IPSET_ATTR_CADT_FLAGS")

        assert flags & IPSET_FLAG_WITH_FORCEADD
        self.ip.destroy(name)

    def test_flush(self):
        require_user('root')
        name = str(uuid4())[:16]
        self.ip.create(name)
        ip_a = "1.1.1.1"
        ip_b = "1.2.3.4"
        self.ip.add(name, ip_a)
        self.ip.add(name, ip_b)
        assert ip_a in self.list_ipset(name)
        assert ip_b in self.list_ipset(name)
        self.ip.flush(name)
        assert ip_a not in self.list_ipset(name)
        assert ip_b not in self.list_ipset(name)
        self.ip.destroy(name)

    def test_rename(self):
        require_user('root')
        name = str(uuid4())[:16]
        name_bis = str(uuid4())[:16]
        self.ip.create(name)
        self.ip.rename(name, name_bis)
        assert self.get_ipset(name_bis)
        self.ip.destroy(name_bis)

    def test_timeout(self):
        require_user('root')
        name = str(uuid4())[:16]
        ip = "1.2.3.4"
        self.ip.create(name, timeout=1)
        self.ip.add(name, ip)
        sleep(2)
        assert ip not in self.list_ipset(name)
        # check that we can overwrite default timeout value
        self.ip.add(name, ip, timeout=5)
        sleep(2)
        assert ip in self.list_ipset(name)
        assert self.list_ipset(name)[ip][3] > 0  # timeout
        sleep(3)
        assert ip not in self.list_ipset(name)
        self.ip.destroy(name)

    def test_net_and_iface_stypes(self):
        require_user('root')
        name = str(uuid4())[:16]
        test_values = (('hash:net', ('192.168.1.0/31', '192.168.12.0/24')),
                       ('hash:net,iface', ('192.168.1.0/24,eth0',
                                           '192.168.2.0/24,wlan0')))
        for stype, test_values in test_values:
            self.ip.create(name, stype=stype)
            etype = stype.split(':', 1)[1]
            assert self.get_ipset(name)
            for entry in test_values:
                self.ip.add(name, entry, etype=etype)
                assert entry in self.list_ipset(name)
                self.ip.delete(name, entry, etype=etype)
                assert entry not in self.list_ipset(name)
            self.ip.destroy(name)
            assert not self.get_ipset(name)

    def test_tuple_support(self):
        require_user('root')
        name = str(uuid4())[:16]
        test_values = (('hash:net,iface', (('192.168.1.0/24', 'eth0'),
                                           ('192.168.2.0/24', 'wlan0'))),)
        for stype, test_values in test_values:
            self.ip.create(name, stype=stype)
            etype = stype.split(':', 1)[1]
            assert self.get_ipset(name)
            for entry in test_values:
                self.ip.add(name, entry, etype=etype)
                assert self.ip.test(name, entry, etype=etype)
                self.ip.delete(name, entry, etype=etype)
                assert not self.ip.test(name, entry, etype=etype)
            self.ip.destroy(name)
            assert not self.get_ipset(name)

    def test_net_with_dash(self):
        require_user('root')
        name = str(uuid4())[:16]
        stype = "hash:net"
        self.ip.create(name, stype=stype)
        # The kernel will split this kind of strings to subnets
        self.ip.add(name, "192.168.1.0-192.168.1.33", etype="net")
        assert "192.168.1.0/27" in self.list_ipset(name)
        assert "192.168.1.32/31" in self.list_ipset(name)
        self.ip.destroy(name)

    def test_double_net(self):
        require_user('root')
        name = str(uuid4())[:16]
        stype = "hash:net,port,net"
        etype = "net,port,net"
        self.ip.create(name, stype=stype)
        port = PortEntry(80, protocol=socket.getprotobyname("tcp"))

        self.ip.add(name, ("192.168.0.0/24", port, "192.168.2.0/24"),
                    etype=etype)
        self.ip.destroy(name)

    def test_custom_hash_values(self):
        require_user('root')
        name = str(uuid4())[:16]
        stype = "hash:net"
        maxelem = 16384
        hashsize = 64
        self.ip.create(name, stype=stype, maxelem=maxelem, hashsize=hashsize)

        res = self.ip.list(name)[0].get_attr("IPSET_ATTR_DATA")

        assert res.get_attr("IPSET_ATTR_HASHSIZE") == hashsize
        assert res.get_attr("IPSET_ATTR_MAXELEM") == maxelem
        assert res.get_attr("IPSET_ATTR_REFERENCES") == 0

        self.ip.destroy(name)

    def test_list_set(self):
        require_user('root')
        name = str(uuid4())[:16]
        subname = str(uuid4())[:16]
        subtype = "hash:net"

        self.ip.create(subname, stype=subtype)
        self.ip.create(name, "list:set")

        self.ip.add(name, subname, etype="set")
        assert subname in self.list_ipset(name)
        assert self.ip.test(name, subname, etype="set")

        res = self.ip.list(subname)[0].get_attr("IPSET_ATTR_DATA")
        assert res.get_attr("IPSET_ATTR_REFERENCES") == 1

        self.ip.delete(name, subname, etype="set")
        assert subname not in self.list_ipset(name)
        self.ip.destroy(subname)
        self.ip.destroy(name)

    def test_bitmap_port(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipset_type = "bitmap:port"
        etype = "port"
        port_range = (1000, 6000)

        self.ip.create(name, stype=ipset_type, bitmap_ports_range=port_range)
        self.ip.add(name, 1002, etype=etype)
        assert self.ip.test(name, 1002, etype=etype)

        add_range = PortRange(2000, 3000, protocol=None)
        self.ip.add(name, add_range, etype=etype)
        assert self.ip.test(name, 2001, etype=etype)
        assert self.ip.test(name, 3000, etype=etype)
        assert not self.ip.test(name, 4000, etype=etype)

        # Check that delete is working as well
        self.ip.delete(name, add_range, etype=etype)
        assert not self.ip.test(name, 2001, etype=etype)

        # Test PortEntry without protocol set
        port_entry = PortEntry(2001)
        self.ip.add(name, port_entry, etype=etype)
        try:
            self.ip.add(name, 18, etype=etype)
            assert False
        except NetlinkError as e:
            assert e.code == IPSET_ERR_TYPE_SPECIFIC
        self.ip.destroy(name)

    def test_port_range_with_proto(self):
        require_user('root')
        name = str(uuid4())[:16]
        ipset_type = "hash:net,port"
        etype = "net,port"
        port_range = PortRange(1000, 2000, protocol=socket.IPPROTO_UDP)
        port_entry = PortEntry(1001, protocol=socket.IPPROTO_UDP)

        self.ip.create(name, stype=ipset_type)
        self.ip.add(name, ("192.0.2.0/24", port_range), etype=etype)

        assert self.ip.test(name, ("192.0.2.0/24", port_range), etype=etype)
        assert self.ip.test(name, ("192.0.2.2/32", port_entry), etype=etype)
        # change protocol, that should not be in
        port_range.protocol = socket.IPPROTO_TCP
        assert not self.ip.test(name, ("192.0.2.0/24", port_range),
                                etype="net,port")
        port_entry.port = 2
        assert not self.ip.test(name, ("192.0.2.0/24", port_entry),
                                etype="net,port")

        # same example than in ipset man pages
        proto = socket.getprotobyname("vrrp")
        port_entry.port = 0
        port_entry.protocol = proto
        self.ip.add(name, ("192.0.2.0/24", port_entry), etype=etype)
        self.ip.test(name, ("192.0.2.0/24", port_entry), etype=etype)

        self.ip.destroy(name)
