import errno
import pytest
from time import sleep
from pyroute2.ipset import IPSet, IPSetError, PortRange, PortEntry
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.nfnetlink.ipset import IPSET_FLAG_WITH_FORCEADD
from pyroute2.netlink.nfnetlink.ipset import IPSET_ERR_TYPE_SPECIFIC
from uuid import uuid4

import socket


def parse_ip(entry):
    ip_from = entry.get_attr('IPSET_ATTR_IP_FROM')
    return ip_from.get_attr('IPSET_ATTR_IPADDR_IPV4')


def parse_net(entry):
    net = parse_ip(entry)
    cidr = entry.get_attr("IPSET_ATTR_CIDR")
    if cidr is not None:
        net += '/{0}'.format(cidr)
    return net


def ipset_type_to_entry_type(ipset_type):
    return ipset_type.split(':', 1)[1].split(',')


def list_ipset(name):
    with IPSet() as sock:
        res = {}
        msg_list = sock.list(name)
        adt = 'IPSET_ATTR_ADT'
        proto = 'IPSET_ATTR_DATA'
        stype = 'IPSET_ATTR_TYPENAME'
        for msg in msg_list:
            for x in msg.get_attr(adt).get_attrs(proto):
                entry = ''
                msg_stypes = msg.get_attr(stype)
                if msg_stypes is None:
                    msg_stypes = 'hash:ip'
                for st in ipset_type_to_entry_type(msg_stypes):
                    if st == "ip":
                        entry = parse_ip(x)
                    elif st == "net":
                        entry = parse_net(x)
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


def ipset_exists(name):
    with IPSet() as sock:
        try:
            sock.headers(name)
            return True
        except IPSetError as e:
            if e.code == errno.ENOENT:
                return False
            raise


def test_create_exclusive_fail(ipset):
    name = str(uuid4())[:16]
    ipset.create(name)
    assert ipset_exists(name)
    try:
        ipset.create(name)
    except NetlinkError as e:
        if e.code != errno.EEXIST:
            raise
    finally:
        ipset.destroy(name)


def test_create_exclusive_success(ipset):
    name = str(uuid4())[:16]
    ipset.create(name)
    assert ipset_exists(name)
    ipset.create(name, exclusive=False)
    ipset.destroy(name)


def test_add_exclusive_fail(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    ipset.create(name)
    ipset.add(name, ipaddr)
    assert ipaddr in list_ipset(name)
    try:
        ipset.add(name, ipaddr)
    except NetlinkError:
        pass
    finally:
        ipset.destroy(name)


def test_add_exclusive_success(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    ipset.create(name)
    ipset.add(name, ipaddr)
    assert ipaddr in list_ipset(name)
    ipset.add(name, ipaddr, exclusive=False)
    ipset.destroy(name)
    assert not ipset_exists(name)


def test_create_destroy(ipset):
    name = str(uuid4())[:16]
    # create ipset
    ipset.create(name)
    # assert it exists
    assert ipset_exists(name)
    # remove ipset
    ipset.destroy(name)
    # assert it is removed
    assert not ipset_exists(name)


def test_add_delete(ipset):
    name = str(uuid4())[:16]
    ipaddr = '192.168.1.1'
    # create ipset
    ipset.create(name)
    assert ipset_exists(name)
    # add an entry
    ipset.add(name, ipaddr)
    # check it
    assert ipaddr in list_ipset(name)
    # delete an entry
    ipset.delete(name, ipaddr)
    # check it
    assert ipaddr not in list_ipset(name)
    # remove ipset
    ipset.destroy(name)


def test_swap(ipset):
    name_a = str(uuid4())[:16]
    name_b = str(uuid4())[:16]
    ipaddr_a = '192.168.1.1'
    ipaddr_b = '10.0.0.1'

    # create sets
    ipset.create(name_a)
    ipset.create(name_b)
    # add ips
    ipset.add(name_a, ipaddr_a)
    ipset.add(name_b, ipaddr_b)
    assert ipaddr_a in list_ipset(name_a)
    assert ipaddr_b in list_ipset(name_b)
    # swap sets
    ipset.swap(name_a, name_b)
    assert ipaddr_a in list_ipset(name_b)
    assert ipaddr_b in list_ipset(name_a)
    # remove sets
    ipset.destroy(name_a)
    ipset.destroy(name_b)


def test_counters(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    ipset.create(name, counters=True)
    ipset.add(name, ipaddr)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][0] == 0  # Bytes
    assert list_ipset(name)[ipaddr][1] == 0  # Packets
    ipset.destroy(name)

    ipset.create(name, counters=False)
    ipset.add(name, ipaddr)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][0] is None
    assert list_ipset(name)[ipaddr][1] is None
    ipset.destroy(name)


def test_comments(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    comment = 'a very simple comment'
    ipset.create(name, comment=True)
    ipset.add(name, ipaddr, comment=comment)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][2] == comment
    ipset.destroy(name)


def test_skbmark(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    skbmark = (0x100, 0xffffffff)
    ipset.create(name, skbinfo=True)
    ipset.add(name, ipaddr, skbmark=skbmark)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][4] == skbmark
    ipset.destroy(name)


def test_skbprio(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    skbprio = (1, 10)
    ipset.create(name, skbinfo=True)
    ipset.add(name, ipaddr, skbprio=skbprio)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][5] == skbprio
    ipset.destroy(name)


def test_skbqueue(ipset):
    name = str(uuid4())[:16]
    ipaddr = '172.16.202.202'
    skbqueue = 1
    ipset.create(name, skbinfo=True)
    ipset.add(name, ipaddr, skbqueue=skbqueue)
    assert ipaddr in list_ipset(name)
    assert list_ipset(name)[ipaddr][6] == skbqueue
    ipset.destroy(name)


def test_maxelem(ipset):
    name = str(uuid4())[:16]
    ipset.create(name, maxelem=1)
    data = ipset.list(name)[0].get_attr("IPSET_ATTR_DATA")
    maxelem = data.get_attr("IPSET_ATTR_MAXELEM")
    ipset.destroy(name)
    assert maxelem == 1


def test_hashsize(ipset):
    name = str(uuid4())[:16]
    min_size = 64
    ipset.create(name, hashsize=min_size)
    data = ipset.list(name)[0].get_attr("IPSET_ATTR_DATA")
    hashsize = data.get_attr("IPSET_ATTR_HASHSIZE")
    ipset.destroy(name)
    assert hashsize == min_size


def test_forceadd(ipset):
    name = str(uuid4())[:16]
    ipset.create(name, forceadd=True)
    res = ipset.list(name)[0].get_attr("IPSET_ATTR_DATA")
    flags = res.get_attr("IPSET_ATTR_CADT_FLAGS")
    assert flags & IPSET_FLAG_WITH_FORCEADD
    ipset.destroy(name)


def test_flush(ipset):
    name = str(uuid4())[:16]
    ipset.create(name)
    ip_a = "1.1.1.1"
    ip_b = "1.2.3.4"
    ipset.add(name, ip_a)
    ipset.add(name, ip_b)
    assert ip_a in list_ipset(name)
    assert ip_b in list_ipset(name)
    ipset.flush(name)
    assert ip_a not in list_ipset(name)
    assert ip_b not in list_ipset(name)
    ipset.destroy(name)


def test_rename(ipset):
    name = str(uuid4())[:16]
    name_bis = str(uuid4())[:16]
    ipset.create(name)
    ipset.rename(name, name_bis)
    assert ipset_exists(name_bis)
    assert not ipset_exists(name)
    ipset.destroy(name_bis)


def test_timeout(ipset):
    name = str(uuid4())[:16]
    ip = "1.2.3.4"
    ipset.create(name, timeout=1)
    ipset.add(name, ip)
    sleep(2)
    assert ip not in list_ipset(name)
    # check that we can overwrite default timeout value
    ipset.add(name, ip, timeout=5)
    sleep(2)
    assert ip in list_ipset(name)
    assert list_ipset(name)[ip][3] > 0  # timeout
    sleep(3)
    assert ip not in list_ipset(name)
    ipset.destroy(name)


def test_net_and_iface_stypes(ipset):
    name = str(uuid4())[:16]
    test_values = (('hash:net', ('192.168.1.0/31', '192.168.12.0/24')),
                   ('hash:net,iface', ('192.168.1.0/24,eth0',
                                       '192.168.2.0/24,wlan0')))
    for stype, test_values in test_values:
        ipset.create(name, stype=stype)
        etype = stype.split(':', 1)[1]
        assert ipset_exists(name)
        for entry in test_values:
            ipset.add(name, entry, etype=etype)
            assert entry in list_ipset(name)
            ipset.delete(name, entry, etype=etype)
            assert entry not in list_ipset(name)
        ipset.destroy(name)
        assert not ipset_exists(name)


def test_tuple_support(ipset):
    name = str(uuid4())[:16]
    test_values = (('hash:net,iface', (('192.168.1.0/24', 'eth0'),
                                       ('192.168.2.0/24', 'wlan0'))),)
    for stype, test_values in test_values:
        ipset.create(name, stype=stype)
        etype = stype.split(':', 1)[1]
        assert ipset_exists(name)
        for entry in test_values:
            ipset.add(name, entry, etype=etype)
            assert ipset.test(name, entry, etype=etype)
            ipset.delete(name, entry, etype=etype)
            assert not ipset.test(name, entry, etype=etype)
        ipset.destroy(name)
        assert not ipset_exists(name)


def test_net_with_dash(ipset):
    name = str(uuid4())[:16]
    stype = "hash:net"
    ipset.create(name, stype=stype)
    # The kernel will split this kind of strings to subnets
    ipset.add(name, "192.168.1.0-192.168.1.33", etype="net")
    assert "192.168.1.0/27" in list_ipset(name)
    assert "192.168.1.32/31" in list_ipset(name)
    ipset.destroy(name)


def test_double_net(ipset):
    name = str(uuid4())[:16]
    stype = "hash:net,port,net"
    etype = "net,port,net"
    ipset.create(name, stype=stype)
    port = PortEntry(80, protocol=socket.getprotobyname("tcp"))

    ipset.add(name, ("192.168.0.0/24", port, "192.168.2.0/24"),
                etype=etype)
    ipset.destroy(name)


def test_custom_hash_values(ipset):
    name = str(uuid4())[:16]
    stype = "hash:net"
    maxelem = 16384
    hashsize = 64
    ipset.create(name, stype=stype, maxelem=maxelem, hashsize=hashsize)

    res = ipset.list(name)[0].get_attr("IPSET_ATTR_DATA")

    assert res.get_attr("IPSET_ATTR_HASHSIZE") == hashsize
    assert res.get_attr("IPSET_ATTR_MAXELEM") == maxelem
    assert res.get_attr("IPSET_ATTR_REFERENCES") == 0

    ipset.destroy(name)


def test_list_set(ipset):
    name = str(uuid4())[:16]
    subname = str(uuid4())[:16]
    subtype = "hash:net"

    ipset.create(subname, stype=subtype)
    ipset.create(name, "list:set")

    ipset.add(name, subname, etype="set")
    assert subname in list_ipset(name)
    assert ipset.test(name, subname, etype="set")

    res = ipset.list(subname)[0].get_attr("IPSET_ATTR_DATA")
    assert res.get_attr("IPSET_ATTR_REFERENCES") == 1

    ipset.delete(name, subname, etype="set")
    assert subname not in list_ipset(name)
    ipset.destroy(subname)
    ipset.destroy(name)


def test_bitmap_port(ipset):
    name = str(uuid4())[:16]
    ipset_type = "bitmap:port"
    etype = "port"
    port_range = (1000, 6000)

    ipset.create(name, stype=ipset_type, bitmap_ports_range=port_range)
    ipset.add(name, 1002, etype=etype)
    assert ipset.test(name, 1002, etype=etype)

    add_range = PortRange(2000, 3000, protocol=None)
    ipset.add(name, add_range, etype=etype)
    assert ipset.test(name, 2001, etype=etype)
    assert ipset.test(name, 3000, etype=etype)
    assert not ipset.test(name, 4000, etype=etype)

    # Check that delete is working as well
    ipset.delete(name, add_range, etype=etype)
    assert not ipset.test(name, 2001, etype=etype)

    # Test PortEntry without protocol set
    port_entry = PortEntry(2001)
    ipset.add(name, port_entry, etype=etype)
    try:
        ipset.add(name, 18, etype=etype)
        assert False
    except NetlinkError as e:
        assert e.code == IPSET_ERR_TYPE_SPECIFIC
    ipset.destroy(name)


def test_port_range_with_proto(ipset):
    name = str(uuid4())[:16]
    ipset_type = "hash:net,port"
    etype = "net,port"
    port_range = PortRange(1000, 2000, protocol=socket.IPPROTO_UDP)
    port_entry = PortEntry(1001, protocol=socket.IPPROTO_UDP)

    ipset.create(name, stype=ipset_type)
    ipset.add(name, ("192.0.2.0/24", port_range), etype=etype)

    assert ipset.test(name, ("192.0.2.0/24", port_range), etype=etype)
    assert ipset.test(name, ("192.0.2.2/32", port_entry), etype=etype)
    # change protocol, that should not be in
    port_range.protocol = socket.IPPROTO_TCP
    assert not ipset.test(name, ("192.0.2.0/24", port_range),
                          etype="net,port")
    port_entry.port = 2
    assert not ipset.test(name, ("192.0.2.0/24", port_entry),
                          etype="net,port")

    # same example than in ipset man pages
    proto = socket.getprotobyname("vrrp")
    port_entry.port = 0
    port_entry.protocol = proto
    ipset.add(name, ("192.0.2.0/24", port_entry), etype=etype)
    ipset.test(name, ("192.0.2.0/24", port_entry), etype=etype)

    ipset.destroy(name)


def test_set_by(ipset):
    name_a = str(uuid4())[:16]
    old_vers = ipset._proto_version

    # check revision supported by kernel
    msg = ipset.get_proto_version()
    version = msg[0].get_attr("IPSET_ATTR_PROTOCOL")
    if version < 7:
        pytest.skip("Kernel does not support this feature")

    # set version
    ipset._proto_version = 7
    # create set
    ipset.create(name_a)
    # get index
    msg = ipset.get_set_byname(name_a)
    idx = msg[0].get_attr("IPSET_ATTR_INDEX")
    # get set name by index
    msg = ipset.get_set_byindex(idx)
    name_b = msg[0].get_attr("IPSET_ATTR_SETNAME")
    # remove set
    ipset.destroy(name_a)
    # restore version back to original
    ipset._proto_version = old_vers
    assert name_a == name_b
