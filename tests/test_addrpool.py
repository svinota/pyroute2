from pyroute2.common import AddrPool


class TestAddrPool(object):

    def test_alloc_aligned(self):

        ap = AddrPool(minaddr=1, maxaddr=1024)
        for i in range(1024):
            ap.alloc()

        try:
            ap.alloc()
        except KeyError:
            pass

    def test_alloc_odd(self):

        ap = AddrPool(minaddr=1, maxaddr=1020)
        for i in range(1020):
            ap.alloc()

        try:
            ap.alloc()
        except KeyError:
            pass

    def test_reverse(self):

        ap = AddrPool(minaddr=1, maxaddr=1024, reverse=True)
        for i in range(512):
            assert ap.alloc() > ap.alloc()

    def test_free(self):

        ap = AddrPool(minaddr=1, maxaddr=1024)
        f = ap.alloc()
        ap.free(f)

    def test_free_fail(self):

        ap = AddrPool(minaddr=1, maxaddr=1024)
        try:
            ap.free(0)
        except KeyError:
            pass

    def test_free_reverse_fail(self):

        ap = AddrPool(minaddr=1, maxaddr=1024, reverse=True)
        try:
            ap.free(0)
        except KeyError:
            pass
