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
    ip_from = entry.get_attr("IPSET_ATTR_IP_FROM")
    return ip_from.get_attr("IPSET_ATTR_IPADDR_IPV4")


def parse_net(entry):
    net = parse_ip(entry)
    cidr = entry.get_attr("IPSET_ATTR_CIDR")
    if cidr is not None:
        net += "/{0}".format(cidr)
    return net


def ipset_type_to_entry_type(ipset_type):
    return ipset_type.split(":", 1)[1].split(",")


def list_ipset(ipset_name):
    with IPSet() as sock:
        res = {}
        msg_list = sock.list(ipset_name)
        adt = "IPSET_ATTR_ADT"
        proto = "IPSET_ATTR_DATA"
        stype = "IPSET_ATTR_TYPENAME"
        for msg in msg_list:
            for x in msg.get_attr(adt).get_attrs(proto):
                entry = ""
                msg_stypes = msg.get_attr(stype)
                if msg_stypes is None:
                    msg_stypes = "hash:ip"
                for st in ipset_type_to_entry_type(msg_stypes):
                    if st == "ip":
                        entry = parse_ip(x)
                    elif st == "net":
                        entry = parse_net(x)
                    elif st == "iface":
                        entry += x.get_attr("IPSET_ATTR_IFACE")
                    elif st == "set":
                        entry += x.get_attr("IPSET_ATTR_NAME")
                    entry += ","

                entry = entry.strip(",")

                res[entry] = (
                    x.get_attr("IPSET_ATTR_PACKETS"),
                    x.get_attr("IPSET_ATTR_BYTES"),
                    x.get_attr("IPSET_ATTR_COMMENT"),
                    x.get_attr("IPSET_ATTR_TIMEOUT"),
                    x.get_attr("IPSET_ATTR_SKBMARK"),
                    x.get_attr("IPSET_ATTR_SKBPRIO"),
                    x.get_attr("IPSET_ATTR_SKBQUEUE"),
                )
        return res


def ipset_exists(ipset_name):
    with IPSet() as sock:
        try:
            sock.headers(ipset_name)
            return True
        except IPSetError as e:
            if e.code == errno.ENOENT:
                return False
            raise


def test_create_exclusive_fail(ipset, ipset_name):
    ipset.create(ipset_name)
    assert ipset_exists(ipset_name)
    try:
        ipset.create(ipset_name)
    except NetlinkError as e:
        if e.code != errno.EEXIST:
            raise


def test_create_exclusive_success(ipset, ipset_name):
    ipset.create(ipset_name)
    assert ipset_exists(ipset_name)
    ipset.create(ipset_name, exclusive=False)  # do not fail


def test_add_exclusive_fail(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    ipset.create(ipset_name)
    ipset.add(ipset_name, ipaddr)
    assert ipaddr in list_ipset(ipset_name)
    try:
        ipset.add(ipset_name, ipaddr)
    except NetlinkError:
        pass


def test_add_exclusive_success(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    ipset.create(ipset_name)
    ipset.add(ipset_name, ipaddr)
    assert ipaddr in list_ipset(ipset_name)
    ipset.add(ipset_name, ipaddr, exclusive=False)


def test_create_destroy(ipset, ipset_name):
    # create ipset
    ipset.create(ipset_name)
    # assert it exists
    assert ipset_exists(ipset_name)
    # remove ipset
    ipset.destroy(ipset_name)
    # assert it is removed
    assert not ipset_exists(ipset_name)


def test_add_delete(ipset, ipset_name):
    ipaddr = "192.168.1.1"
    # create ipset
    ipset.create(ipset_name)
    assert ipset_exists(ipset_name)
    # add an entry
    ipset.add(ipset_name, ipaddr)
    # check it
    assert ipaddr in list_ipset(ipset_name)
    # delete an entry
    ipset.delete(ipset_name, ipaddr)
    # check it
    assert ipaddr not in list_ipset(ipset_name)


def test_swap(ipset):
    ipset_name_a = str(uuid4())[:16]
    ipset_name_b = str(uuid4())[:16]
    ipaddr_a = "192.168.1.1"
    ipaddr_b = "10.0.0.1"

    # create sets
    ipset.create(ipset_name_a)
    ipset.create(ipset_name_b)
    # add ips
    ipset.add(ipset_name_a, ipaddr_a)
    ipset.add(ipset_name_b, ipaddr_b)
    assert ipaddr_a in list_ipset(ipset_name_a)
    assert ipaddr_b in list_ipset(ipset_name_b)
    # swap sets
    ipset.swap(ipset_name_a, ipset_name_b)
    assert ipaddr_a in list_ipset(ipset_name_b)
    assert ipaddr_b in list_ipset(ipset_name_a)
    # remove sets
    ipset.destroy(ipset_name_a)
    ipset.destroy(ipset_name_b)


def test_counters(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    ipset.create(ipset_name, counters=True)
    ipset.add(ipset_name, ipaddr)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][0] == 0  # Bytes
    assert list_ipset(ipset_name)[ipaddr][1] == 0  # Packets
    ipset.destroy(ipset_name)

    ipset.create(ipset_name, counters=False)
    ipset.add(ipset_name, ipaddr)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][0] is None
    assert list_ipset(ipset_name)[ipaddr][1] is None


def test_comments(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    comment = "a very simple comment"
    ipset.create(ipset_name, comment=True)
    ipset.add(ipset_name, ipaddr, comment=comment)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][2] == comment


def test_skbmark(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    skbmark = (0x100, 0xFFFFFFFF)
    ipset.create(ipset_name, skbinfo=True)
    ipset.add(ipset_name, ipaddr, skbmark=skbmark)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][4] == skbmark


def test_skbprio(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    skbprio = (1, 10)
    ipset.create(ipset_name, skbinfo=True)
    ipset.add(ipset_name, ipaddr, skbprio=skbprio)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][5] == skbprio


def test_skbqueue(ipset, ipset_name):
    ipaddr = "172.16.202.202"
    skbqueue = 1
    ipset.create(ipset_name, skbinfo=True)
    ipset.add(ipset_name, ipaddr, skbqueue=skbqueue)
    assert ipaddr in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ipaddr][6] == skbqueue


def test_maxelem(ipset, ipset_name):
    ipset.create(ipset_name, maxelem=1)
    data = ipset.list(ipset_name)[0].get_attr("IPSET_ATTR_DATA")
    maxelem = data.get_attr("IPSET_ATTR_MAXELEM")
    assert maxelem == 1


def test_hashsize(ipset, ipset_name):
    min_size = 64
    ipset.create(ipset_name, hashsize=min_size)
    data = ipset.list(ipset_name)[0].get_attr("IPSET_ATTR_DATA")
    hashsize = data.get_attr("IPSET_ATTR_HASHSIZE")
    assert hashsize == min_size


def test_forceadd(ipset, ipset_name):
    ipset.create(ipset_name, forceadd=True)
    res = ipset.list(ipset_name)[0].get_attr("IPSET_ATTR_DATA")
    flags = res.get_attr("IPSET_ATTR_CADT_FLAGS")
    assert flags & IPSET_FLAG_WITH_FORCEADD


def test_flush(ipset, ipset_name):
    ipset.create(ipset_name)
    ip_a = "1.1.1.1"
    ip_b = "1.2.3.4"
    ipset.add(ipset_name, ip_a)
    ipset.add(ipset_name, ip_b)
    assert ip_a in list_ipset(ipset_name)
    assert ip_b in list_ipset(ipset_name)
    ipset.flush(ipset_name)
    assert ip_a not in list_ipset(ipset_name)
    assert ip_b not in list_ipset(ipset_name)


def test_rename(ipset, ipset_name):
    ipset_name_bis = str(uuid4())[:16]
    ipset.create(ipset_name)
    ipset.rename(ipset_name, ipset_name_bis)
    assert ipset_exists(ipset_name_bis)
    assert not ipset_exists(ipset_name)


def test_timeout(ipset, ipset_name):
    ip = "1.2.3.4"
    ipset.create(ipset_name, timeout=1)
    ipset.add(ipset_name, ip)
    sleep(2)
    assert ip not in list_ipset(ipset_name)
    # check that we can overwrite default timeout value
    ipset.add(ipset_name, ip, timeout=5)
    sleep(2)
    assert ip in list_ipset(ipset_name)
    assert list_ipset(ipset_name)[ip][3] > 0  # timeout
    sleep(3)
    assert ip not in list_ipset(ipset_name)


def test_net_and_iface_stypes(ipset, ipset_name):
    test_values = (
        ("hash:net", ("192.168.1.0/31", "192.168.12.0/24")),
        ("hash:net,iface", ("192.168.1.0/24,eth0", "192.168.2.0/24,wlan0")),
    )
    for stype, test_values in test_values:
        ipset.create(ipset_name, stype=stype)
        etype = stype.split(":", 1)[1]
        assert ipset_exists(ipset_name)
        for entry in test_values:
            ipset.add(ipset_name, entry, etype=etype)
            assert entry in list_ipset(ipset_name)
            ipset.delete(ipset_name, entry, etype=etype)
            assert entry not in list_ipset(ipset_name)
        ipset.destroy(ipset_name)
        assert not ipset_exists(ipset_name)


def test_tuple_support(ipset, ipset_name):
    test_values = (
        (
            "hash:net,iface",
            (("192.168.1.0/24", "eth0"), ("192.168.2.0/24", "wlan0")),
        ),
    )
    for stype, test_values in test_values:
        ipset.create(ipset_name, stype=stype)
        etype = stype.split(":", 1)[1]
        assert ipset_exists(ipset_name)
        for entry in test_values:
            ipset.add(ipset_name, entry, etype=etype)
            assert ipset.test(ipset_name, entry, etype=etype)
            ipset.delete(ipset_name, entry, etype=etype)
            assert not ipset.test(ipset_name, entry, etype=etype)
        ipset.destroy(ipset_name)


def test_net_with_dash(ipset, ipset_name):
    stype = "hash:net"
    ipset.create(ipset_name, stype=stype)
    # The kernel will split this kind of strings to subnets
    ipset.add(ipset_name, "192.168.1.0-192.168.1.33", etype="net")
    assert "192.168.1.0/27" in list_ipset(ipset_name)
    assert "192.168.1.32/31" in list_ipset(ipset_name)


def test_double_net(ipset, ipset_name):
    stype = "hash:net,port,net"
    etype = "net,port,net"
    ipset.create(ipset_name, stype=stype)
    port = PortEntry(80, protocol=socket.getprotobyname("tcp"))

    ipset.add(
        ipset_name, ("192.168.0.0/24", port, "192.168.2.0/24"), etype=etype
    )


def test_custom_hash_values(ipset, ipset_name):
    stype = "hash:net"
    maxelem = 16384
    hashsize = 64
    ipset.create(ipset_name, stype=stype, maxelem=maxelem, hashsize=hashsize)

    res = ipset.list(ipset_name)[0].get_attr("IPSET_ATTR_DATA")

    assert res.get_attr("IPSET_ATTR_HASHSIZE") == hashsize
    assert res.get_attr("IPSET_ATTR_MAXELEM") == maxelem
    assert res.get_attr("IPSET_ATTR_REFERENCES") == 0


def test_list_set(ipset, ipset_name):
    subname = str(uuid4())[:16]
    subtype = "hash:net"

    ipset.create(subname, stype=subtype)
    ipset.create(ipset_name, "list:set")

    ipset.add(ipset_name, subname, etype="set")
    assert subname in list_ipset(ipset_name)
    assert ipset.test(ipset_name, subname, etype="set")

    res = ipset.list(subname)[0].get_attr("IPSET_ATTR_DATA")
    assert res.get_attr("IPSET_ATTR_REFERENCES") == 1

    ipset.delete(ipset_name, subname, etype="set")
    assert subname not in list_ipset(ipset_name)
    ipset.destroy(subname)


def test_bitmap_port(ipset, ipset_name):
    ipset_type = "bitmap:port"
    etype = "port"
    port_range = (1000, 6000)

    ipset.create(ipset_name, stype=ipset_type, bitmap_ports_range=port_range)
    ipset.add(ipset_name, 1002, etype=etype)
    assert ipset.test(ipset_name, 1002, etype=etype)

    add_range = PortRange(2000, 3000, protocol=None)
    ipset.add(ipset_name, add_range, etype=etype)
    assert ipset.test(ipset_name, 2001, etype=etype)
    assert ipset.test(ipset_name, 3000, etype=etype)
    assert not ipset.test(ipset_name, 4000, etype=etype)

    # Check that delete is working as well
    ipset.delete(ipset_name, add_range, etype=etype)
    assert not ipset.test(ipset_name, 2001, etype=etype)

    # Test PortEntry without protocol set
    port_entry = PortEntry(2001)
    ipset.add(ipset_name, port_entry, etype=etype)
    try:
        ipset.add(ipset_name, 18, etype=etype)
        assert False
    except NetlinkError as e:
        assert e.code == IPSET_ERR_TYPE_SPECIFIC


def test_port_range_with_proto(ipset, ipset_name):
    ipset_type = "hash:net,port"
    etype = "net,port"
    port_range = PortRange(1000, 2000, protocol=socket.IPPROTO_UDP)
    port_entry = PortEntry(1001, protocol=socket.IPPROTO_UDP)

    ipset.create(ipset_name, stype=ipset_type)
    ipset.add(ipset_name, ("192.0.2.0/24", port_range), etype=etype)

    assert ipset.test(ipset_name, ("192.0.2.0/24", port_range), etype=etype)
    assert ipset.test(ipset_name, ("192.0.2.2/32", port_entry), etype=etype)
    # change protocol, that should not be in
    port_range.protocol = socket.IPPROTO_TCP
    assert not ipset.test(
        ipset_name, ("192.0.2.0/24", port_range), etype="net,port"
    )
    port_entry.port = 2
    assert not ipset.test(
        ipset_name, ("192.0.2.0/24", port_entry), etype="net,port"
    )

    # same example than in ipset man pages
    proto = socket.getprotobyname("vrrp")
    port_entry.port = 0
    port_entry.protocol = proto
    ipset.add(ipset_name, ("192.0.2.0/24", port_entry), etype=etype)
    ipset.test(ipset_name, ("192.0.2.0/24", port_entry), etype=etype)


def test_set_by(ipset, ipset_name):
    old_vers = ipset._proto_version

    # check revision supported by kernel
    msg = ipset.get_proto_version()
    version = msg[0].get_attr("IPSET_ATTR_PROTOCOL")
    if version < 7:
        pytest.skip("Kernel does not support this feature")

    # set version
    ipset._proto_version = 7
    # create set
    ipset.create(ipset_name)
    # get index
    msg = ipset.get_set_byname(ipset_name)
    idx = msg[0].get_attr("IPSET_ATTR_INDEX")
    # get set name by index
    msg = ipset.get_set_byindex(idx)
    name_found = msg[0].get_attr("IPSET_ATTR_SETNAME")
    # restore version back to original
    ipset._proto_version = old_vers
    assert ipset_name == name_found
