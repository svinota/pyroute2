import pytest

from pyroute2.common import AddrPool


def test_alloc_aligned():
    ap = AddrPool(minaddr=1, maxaddr=1024)
    for i in range(1024):
        ap.alloc()
    with pytest.raises(KeyError):
        ap.alloc()


def test_alloc_odd():
    ap = AddrPool(minaddr=1, maxaddr=1020)
    for i in range(1020):
        ap.alloc()
    with pytest.raises(KeyError):
        ap.alloc()


def test_reverse():
    ap = AddrPool(minaddr=1, maxaddr=1024, reverse=True)
    for i in range(512):
        assert ap.alloc() > ap.alloc()


def test_free():
    ap = AddrPool(minaddr=1, maxaddr=1024)
    f = ap.alloc()
    ap.free(f)


def test_free_fail():
    ap = AddrPool(minaddr=1, maxaddr=1024)
    with pytest.raises(KeyError):
        ap.free(0)


def test_free_reverse_fail():
    ap = AddrPool(minaddr=1, maxaddr=1024, reverse=True)
    with pytest.raises(KeyError):
        ap.free(0)


def test_locate():
    ap = AddrPool()
    f = ap.alloc()
    base1, bit1, is_allocated1 = ap.locate(f)
    base2, bit2, is_allocated2 = ap.locate(f + 1)
    assert base1 == base2
    assert bit2 == bit1 + 1
    assert is_allocated1
    assert not is_allocated2
    assert ap.allocated == 1


def test_setaddr_allocated():
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


def test_setaddr_free():
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
    with pytest.raises(KeyError):
        ap.free(f)
