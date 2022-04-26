from time import sleep

from pyroute2.netlink.exceptions import IPSetError
from pyroute2.wiset import IPStats
from pyroute2.wiset import WiSet
from pyroute2.wiset import get_ipset_socket
from pyroute2.wiset import load_all_ipsets
from pyroute2.wiset import load_ipset
from pyroute2.wiset import test_ipset_exist as ipset_exists

from utils import require_kernel


def test_create_one_ipset(ipset_name, wiset_sock):
    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        myset.create()

        list_wiset = load_all_ipsets(sock=wiset_sock)
        assert ipset_exists(ipset_name, sock=wiset_sock)
        myset.destroy()

        assert not ipset_exists(ipset_name, sock=wiset_sock)
        assert ipset_name in list_wiset
        assert ipset_name not in load_all_ipsets(sock=wiset_sock)


def test_create_ipset_twice(ipset_name, wiset_sock):
    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        myset.create()

        try:
            myset.create(exclusive=True)
            assert False
        except IPSetError:
            pass

        myset.create(exclusive=False)
        myset.destroy()
        assert ipset_name not in load_all_ipsets(sock=wiset_sock)


def test_check_ipset_stats(ipset_name, wiset_sock):
    def test_stats(myset, res=None, counters=False):
        myset.counters = counters
        myset.create()
        myset.add("8.8.8.8", packets=res, bytes=res)
        myset.update_content()
        stats = myset.content
        myset.flush()

        assert stats["8.8.8.8"].packets == res
        assert stats["8.8.8.8"].bytes == res

        myset.add("8.8.8.8")
        myset.update_content()
        stats = myset.content
        if res is not None:
            res = 0
        assert stats["8.8.8.8"].packets == res
        assert stats["8.8.8.8"].bytes == res
        myset.destroy()

    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        test_stats(myset, res=10, counters=True)
        test_stats(myset)


def test_ipset_with_comment(ipset_name, wiset_sock):
    comment = "test comment"

    with WiSet(name=ipset_name, sock=wiset_sock, comment=True) as myset:
        myset.create()
        myset.add("8.8.8.8", comment=comment)
        set_list = myset.content

    assert set_list["8.8.8.8"].comment == comment


def test_ipset_with_skbinfo(ipset_name, wiset_sock):
    with WiSet(name=ipset_name, sock=wiset_sock, skbinfo=True) as myset:
        myset.create()
        myset.add("192.168.1.1", skbmark=(0xC8, 0xC8))
        myset.add("192.168.1.2", skbmark=(0xC9, 0xFFFFFFFF))
        myset.add("192.168.1.3", skbmark="0xca/0xca")
        myset.add("192.168.1.4", skbmark="0xCB")
        set_list = myset.content
        myset.destroy()

    assert set_list["192.168.1.1"].skbmark == "0xc8/0xc8"
    assert set_list["192.168.1.2"].skbmark == "0xc9"
    assert set_list["192.168.1.3"].skbmark == "0xca/0xca"
    assert set_list["192.168.1.4"].skbmark == "0xcb"


def test_list_on_large_set(ipset_name, wiset_sock):
    set_size = 30000
    base_ip = "10.10.%d.%d"

    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        myset.create()
        for i in range(0, set_size):
            myset.add(base_ip % (i / 255, i % 255))
        stats_len = len(myset.content)
        stats_len2 = len(
            load_ipset(ipset_name, content=True, sock=wiset_sock).content
        )

    assert stats_len == set_size
    assert stats_len2 == set_size


def test_remove_entry(ipset_name, wiset_sock):
    ip = "1.1.1.1"

    with WiSet(name=ipset_name, sock=wiset_sock, counters=True) as myset:
        myset.create()
        myset.add(ip)
        assert ip in myset.content
        myset.delete(ip)
        myset.update_content()
        assert ip not in myset.content


def test_flush(ipset_name, wiset_sock):
    ip_list = ["1.2.3.4", "1.1.1.1", "7.7.7.7"]

    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        myset.create()
        for ip in ip_list:
            myset.add(ip)
            assert myset.test(ip)
        myset.flush()
        for ip in ip_list:
            assert not myset.test(ip)


def test_list_in(ipset_name, wiset_sock):
    ip_list_good = ["1.2.3.4", "1.1.1.1", "7.7.7.7"]
    ip_list_bad = ["4.4.4.4", "5.5.5.5", "6.6.6.6"]

    with WiSet(name=ipset_name, sock=wiset_sock) as myset:
        myset.create()
        myset.replace_entries(ip_list_good)
        res_test = myset.test_list(ip_list_good + ip_list_bad)
        for ip in ip_list_good:
            assert ip in res_test
        for ip in ip_list_bad:
            assert ip not in res_test


def test_timeout(ipset_name, wiset_sock):
    ip = "1.2.3.4"
    timeout = 2

    with WiSet(name=ipset_name, sock=wiset_sock, timeout=timeout) as myset:
        myset.create()
        myset.add(ip)
        sleep(3)
        myset.update_content()
        assert ip not in myset.content
        assert timeout == load_ipset(ipset_name, sock=wiset_sock).timeout
        myset.add(ip, timeout=0)
        myset.update_content()
        assert myset.content[ip].timeout == 0


def test_basic_attribute_reads(ipset_name, wiset_sock):
    for value in [True, False]:
        myset = WiSet(
            name=ipset_name, sock=wiset_sock, counters=value, comment=value
        )
        if wiset_sock is None:
            myset.open_netlink()
        myset.create()
        from_netlink = load_ipset(ipset_name, sock=wiset_sock)
        assert value == from_netlink.comment
        assert value == from_netlink.counters
        myset.destroy()
        if wiset_sock is None:
            myset.close_netlink()


def test_replace_content(ipset_name, wiset_sock):
    list_a = ["1.2.3.4", "2.3.4.5", "6.7.8.9"]
    list_b = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]

    def test_replace(content_a, content_b):
        myset = WiSet(name=ipset_name, sock=wiset_sock)
        myset.create()
        myset.insert_list(content_a)
        myset.update_content()
        for value in content_a:
            assert value in myset.content
        myset.replace_entries(content_b)
        myset.update_content()
        for (old, new) in zip(content_a, content_b):
            assert old not in myset.content
            assert new in myset.content
        myset.destroy()

    test_replace(list_a, list_b)
    test_replace(set(list_a), set(list_b))


def test_replace_content_with_comment(ipset_name, wiset_sock):
    list_a = [
        {'entry': "1.2.3.4", 'comment': 'foo'},
        {'entry': "2.3.4.5", 'comment': 'foo'},
        {'entry': "6.7.8.9", 'comment': 'bar'},
    ]
    list_b = [
        {'entry': "1.1.1.1", 'comment': 'foo'},
        {'entry': "2.2.2.2", 'comment': 'bar'},
        {'entry': "3.3.3.3", 'comment': 'foo'},
    ]

    def test_replace(content_a, content_b):
        myset = WiSet(name=ipset_name, sock=wiset_sock, comment=True)
        myset.create()
        myset.insert_list(content_a)
        myset.update_content()
        for value in content_a:
            assert value['entry'] in myset.content
            assert value['comment'] == (myset.content[value['entry']].comment)
        myset.replace_entries(content_b)
        myset.update_content()
        for value in content_a:
            assert value['entry'] not in myset.content
        for value in content_b:
            assert value['entry'] in myset.content
            assert value['comment'] == (myset.content[value['entry']].comment)

    test_replace(list_a, list_b)


def test_hash_net_ipset(ipset_name, wiset_sock):
    to_add = ["192.168.1.0/24", "192.168.2.0/23", "10.0.0.0/8"]
    atype = "hash:net"

    with WiSet(name=ipset_name, attr_type=atype, sock=wiset_sock) as myset:
        myset.create()
        myset.insert_list(to_add)
        for value in to_add:
            assert value in myset.content


def test_two_dimensions_ipset(ipset_name, wiset_sock):
    to_add = ["192.168.1.0/24,eth0", "192.168.2.0/23,eth1", "10.0.0.0/8,tun0"]
    atype = "hash:net,iface"

    with WiSet(name=ipset_name, attr_type=atype, sock=wiset_sock) as myset:
        myset.create()
        myset.insert_list(to_add)
        for value in to_add:
            assert value in myset.content


def test_stats_consistency(ipset_name, wiset_sock):
    """Test several way to fill the statistics of one IPSet"""
    entries = ["1.2.3.4", "1.2.3.5", "1.2.3.6"]

    myset = WiSet(name=ipset_name, sock=wiset_sock)
    myset.create()
    myset.insert_list(entries)

    myset_lists = load_all_ipsets(sock=wiset_sock, content=True)[ipset_name]
    for value in entries:
        assert value in myset_lists.content

    myset_list = load_ipset(ipset_name, sock=wiset_sock, content=True)
    for value in entries:
        assert value in myset_list.content


def test_hashnet_with_comment(ipset_name, wiset_sock):
    comment = "abcdef"
    myset = WiSet(
        name=ipset_name, attr_type="hash:net", comment=True, sock=wiset_sock
    )
    myset.create()

    inherit_sock = wiset_sock is not None
    myset = load_ipset(ipset_name, sock=wiset_sock, inherit_sock=inherit_sock)
    assert myset.comment

    myset.add("192.168.1.1", comment=comment)
    myset.update_content()

    assert myset.content["192.168.1.1/32"].comment == comment


def test_add_ipstats(ipset_name, wiset_sock):
    data = IPStats(
        packets=10,
        bytes=1000,
        comment="hello world",
        skbmark="0x10/0x10",
        timeout=None,
    )
    myset = WiSet(
        name=ipset_name,
        attr_type="hash:net",
        comment=True,
        skbinfo=True,
        counters=True,
        sock=wiset_sock,
    )
    myset.create()
    myset.add("198.51.100.0/24", **data._asdict())

    assert "198.51.100.0/24" in myset.content
    assert data == myset.content["198.51.100.0/24"]


def test_revision(ipset_name, wiset_sock):
    myset = WiSet(name=ipset_name, attr_type="hash:net", sock=wiset_sock)

    myset.create()
    assert load_ipset(ipset_name, sock=wiset_sock).revision >= 6


def test_force_attr_revision(ipset_name, wiset_sock):
    sock = get_ipset_socket(attr_revision=2)

    myset = WiSet(name=ipset_name, attr_type="hash:net", sock=wiset_sock)
    myset.create()
    assert load_ipset(ipset_name, sock=wiset_sock).revision >= 2
    sock.close()


def test_physdev(ipset_name):
    myset = WiSet(name=ipset_name, attr_type="hash:net,iface")
    myset.create()
    myset.add("192.168.0.0/24,eth0", physdev=False)
    myset.add("192.168.1.0/24,eth0", physdev=True)

    content = myset.content

    assert content["192.168.0.0/24,eth0"].physdev is False
    assert content["192.168.1.0/24,eth0"].physdev is True


def test_wildcard_entries(ipset_name):
    require_kernel(5, 5)
    myset = WiSet(name=ipset_name, attr_type="hash:net,iface")
    myset.create()
    myset.add("192.168.0.0/24,eth", wildcard=True)
    myset.add("192.168.1.0/24,wlan0", wildcard=False)

    content = myset.content

    assert content["192.168.0.0/24,eth"].wildcard is True
    assert content["192.168.1.0/24,wlan0"].wildcard is False


def test_invalid_load_ipset():
    assert load_ipset("ipsetdoesnotexists") is None
