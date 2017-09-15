from time import sleep

from pyroute2.common import uifname
from pyroute2.netlink.exceptions import IPSetError
from pyroute2.wiset import WiSet, load_all_ipsets, COUNT, get_ipset_socket
from pyroute2.wiset import test_ipset_exist, load_ipset
from utils import require_user


class WiSet_test(object):

    def setUp(self):
        self.name = uifname()

    def test_create_one_ipset(self, sock=None):
        require_user('root')
        with WiSet(name=self.name, sock=sock) as myset:
            myset.create()

            list_wiset = load_all_ipsets(sock=sock)
            assert test_ipset_exist(self.name, sock=sock)
            myset.destroy()

            assert not test_ipset_exist(self.name, sock=sock)
            assert self.name in list_wiset
            assert self.name not in load_all_ipsets(sock=sock)

    def test_create_ipset_twice(self, sock=None):
        require_user('root')
        with WiSet(name=self.name, sock=sock) as myset:
            myset.create()

            try:
                myset.create(exclusive=True)
                assert False
            except IPSetError:
                pass

            myset.create(exclusive=False)
            myset.destroy()
            assert self.name not in load_all_ipsets(sock=sock)

    def test_check_ipset_stats(self, sock=None):
        require_user('root')

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

        with WiSet(name=self.name, sock=sock) as myset:
            test_stats(myset, res=10, counters=True)
            test_stats(myset)

    def test_ipset_with_comment(self, sock=None):
        require_user('root')
        comment = "test comment"

        with WiSet(name=self.name, sock=sock, comment=True) as myset:
            myset.create()
            myset.add("8.8.8.8", comment=comment)
            set_list = myset.content
            myset.destroy()

        assert set_list["8.8.8.8"].comment == comment

    def test_list_on_large_set(self, sock=None):
        require_user('root')
        set_size = 30000
        base_ip = "10.10.%d.%d"

        with WiSet(name=self.name, sock=sock) as myset:
            myset.create()
            for i in range(0, set_size):
                myset.add(base_ip % (i / 255, i % 255))
            stats_len = len(myset.content)
            stats_len2 = len(load_ipset(self.name, content=True,
                                        sock=sock).content)
            myset.destroy()

        assert stats_len == set_size
        assert stats_len2 == set_size

    def test_remove_entry(self, sock=None):
        require_user('root')
        ip = "1.1.1.1"

        with WiSet(name=self.name, sock=sock, counters=True) as myset:
            myset.create()
            myset.add(ip)
            assert ip in myset.content
            myset.delete(ip)
            myset.update_content()
            assert ip not in myset.content
            myset.destroy()

    def test_flush(self, sock=None):
        require_user('root')
        ip_list = ["1.2.3.4", "1.1.1.1", "7.7.7.7"]

        with WiSet(name=self.name, sock=sock) as myset:
            myset.create()
            for ip in ip_list:
                myset.add(ip)
                assert myset.test(ip)
            myset.flush()
            for ip in ip_list:
                assert not myset.test(ip)
            myset.destroy()

    def test_list_in(self, sock=None):
        require_user('root')
        ip_list_good = ["1.2.3.4", "1.1.1.1", "7.7.7.7"]
        ip_list_bad = ["4.4.4.4", "5.5.5.5", "6.6.6.6"]

        with WiSet(name=self.name, sock=sock) as myset:
            myset.create()
            myset.replace_entries(ip_list_good)
            res_test = myset.test_list(ip_list_good + ip_list_bad)
            for ip in ip_list_good:
                assert ip in res_test
            for ip in ip_list_bad:
                assert ip not in res_test

            myset.destroy()

    def test_timeout(self, sock=None):
        require_user('root')
        ip = "1.2.3.4"
        timeout = 2

        with WiSet(name=self.name, sock=sock, timeout=timeout) as myset:
            myset.create()
            myset.add(ip)
            sleep(3)
            myset.update_content()
            assert ip not in myset.content
            assert timeout == load_ipset(self.name).timeout
            myset.add(ip, timeout=0)
            myset.update_content()
            assert 0 == myset.content[ip].timeout
            myset.destroy()

    def test_basic_attribute_reads(self, sock=None):
        require_user('root')
        for value in [True, False]:
            myset = WiSet(name=self.name, sock=sock, counters=value,
                          comment=value)
            if sock is None:
                myset.open_netlink()
            myset.create()
            from_netlink = load_ipset(self.name, sock=sock)
            assert value == from_netlink.comment
            assert value == from_netlink.counters
            myset.destroy()
            if sock is None:
                myset.close_netlink()

    def test_replace_content(self, sock=None):
        require_user('root')
        list_a = ["1.2.3.4", "2.3.4.5", "6.7.8.9"]
        list_b = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]

        def test_replace(content_a, content_b):
            myset = WiSet(name=self.name, sock=sock)
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

    def test_hash_net_ipset(self, sock=None):
        require_user('root')
        to_add = ["192.168.1.0/24", "192.168.2.0/23", "10.0.0.0/8"]
        atype = "hash:net"

        with WiSet(name=self.name, attr_type=atype, sock=sock) as myset:
            myset.create()
            myset.insert_list(to_add)
            for value in to_add:
                assert value in myset.content
            myset.destroy()

    def test_two_dimensions_ipset(self, sock=None):
        require_user('root')
        to_add = ["192.168.1.0/24,eth0", "192.168.2.0/23,eth1",
                  "10.0.0.0/8,tun0"]
        atype = "hash:net,iface"

        with WiSet(name=self.name, attr_type=atype, sock=sock) as myset:
            myset.create()
            myset.insert_list(to_add)
            for value in to_add:
                assert value in myset.content
            myset.destroy()

    def test_stats_consistency(self, sock=None):
        """ Test several way to fill the statistics of one IPSet """
        require_user('root')
        entries = ["1.2.3.4", "1.2.3.5", "1.2.3.6"]

        myset = WiSet(name=self.name, sock=sock)
        myset.create()
        myset.insert_list(entries)

        myset_lists = load_all_ipsets(sock=sock, content=True)[self.name]
        for value in entries:
            assert value in myset_lists.content

        myset_list = load_ipset(self.name, sock=sock, content=True)
        for value in entries:
            assert value in myset_list.content

        myset.destroy()

    def test_hashnet_with_comment(self, sock=None):
        require_user('root')
        comment = "abcdef"
        myset = WiSet(name=self.name, attr_type="hash:net", comment=True,
                      sock=sock)
        myset.create()

        inherit_sock = sock is not None
        myset = load_ipset(self.name, sock=sock,
                           inherit_sock=inherit_sock)
        assert myset.comment

        myset.add("192.168.1.1", comment=comment)
        myset.update_content()

        assert myset.content["192.168.1.1/32"].comment == comment

        myset.destroy()

    def test_revision(self, sock=None):
        require_user('root')
        myset = WiSet(name=self.name, attr_type="hash:net", sock=sock)

        myset.create()
        assert load_ipset(self.name, sock=sock).revision >= 6

        myset.destroy()

    def test_force_attr_revision(self):
        require_user('root')
        sock = get_ipset_socket(attr_revision=2)

        myset = WiSet(name=self.name, attr_type="hash:net", sock=sock)
        myset.create()
        assert load_ipset(self.name, sock=sock).revision >= 2

        myset.destroy()
        sock.close()

    def test_ipset_context(self):
        before_count = COUNT["count"]
        func = [self.test_create_one_ipset, self.test_create_ipset_twice,
                self.test_check_ipset_stats, self.test_list_on_large_set,
                self.test_remove_entry, self.test_flush,
                self.test_basic_attribute_reads, self.test_replace_content,
                self.test_hash_net_ipset, self.test_stats_consistency,
                self.test_list_in, self.test_hashnet_with_comment,
                self.test_revision]
        for fun in func:
            sock = get_ipset_socket()
            fun(sock=sock)
            assert before_count == COUNT['count']
            sock.close()
