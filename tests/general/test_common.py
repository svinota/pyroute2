from pyroute2.common import AddrPool
from pyroute2.common import hexdump
from pyroute2.common import hexload
from pyroute2.common import uuid32
from pyroute2.common import uifname
from pyroute2.common import dqn2int


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

    def test_locate(self):

        ap = AddrPool()
        f = ap.alloc()
        base1, bit1, is_allocated1 = ap.locate(f)
        base2, bit2, is_allocated2 = ap.locate(f + 1)

        assert base1 == base2
        assert bit2 == bit1 + 1
        assert is_allocated1
        assert not is_allocated2
        assert ap.allocated == 1

    def test_setaddr_allocated(self):

        ap = AddrPool()
        f = ap.alloc()
        base, bit, is_allocated = ap.locate(f + 1)
        assert not is_allocated
        assert ap.allocated == 1
        ap.setaddr(f + 1, 'allocated')
        base, bit, is_allocated = ap.locate(f + 1)
        assert is_allocated
        assert ap.allocated == 2
        ap.free(f + 1)
        base, bit, is_allocated = ap.locate(f + 1)
        assert not is_allocated
        assert ap.allocated == 1

    def test_setaddr_free(self):

        ap = AddrPool()
        f = ap.alloc()
        base, bit, is_allocated = ap.locate(f + 1)
        assert not is_allocated
        assert ap.allocated == 1
        ap.setaddr(f + 1, 'free')
        base, bit, is_allocated = ap.locate(f + 1)
        assert not is_allocated
        assert ap.allocated == 1
        ap.setaddr(f, 'free')
        base, bit, is_allocated = ap.locate(f)
        assert not is_allocated
        assert ap.allocated == 0
        try:
            ap.free(f)
        except KeyError:
            pass


class TestCommon(object):

    def test_hexdump(self):
        binary = b'abcdef5678'
        dump1 = hexdump(binary)
        dump2 = hexdump(binary, length=6)

        assert len(dump1) == 29
        assert len(dump2) == 17
        assert dump1[2] == \
            dump1[-3] == \
            dump2[2] == \
            dump2[-3] == ':'

        assert hexload(dump1) == binary
        assert hexload(dump2) == binary[:6]

    def test_uuid32(self):
        uA = uuid32()
        uB = uuid32()

        prime = __builtins__.get('long', int)
        assert isinstance(uA, prime)
        assert isinstance(uB, prime)
        assert uA != uB
        assert uA < 0x100000000
        assert uB < 0x100000000

    def test_dqn2int(self):
        assert dqn2int('255.255.255.0') == 24
        assert dqn2int('255.240.0.0') == 12
        assert dqn2int('255.0.0.0') == 8

    def test_uifname(self):
        nA = uifname()
        nB = uifname()

        assert nA != nB
        assert int(nA[2:], 16) != int(nB[2:], 16)
