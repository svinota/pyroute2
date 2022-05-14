from pyroute2.common import dqn2int, hexdump, hexload, uifname, uuid32


def test_hexdump():
    binary = b'abcdef5678'
    dump1 = hexdump(binary)
    dump2 = hexdump(binary, length=6)
    assert len(dump1) == 29
    assert len(dump2) == 17
    assert dump1[2] == dump1[-3] == dump2[2] == dump2[-3] == ':'
    assert hexload(dump1) == binary
    assert hexload(dump2) == binary[:6]


def test_uuid32():
    uA = uuid32()
    uB = uuid32()
    prime = __builtins__.get('long', int)
    assert isinstance(uA, prime)
    assert isinstance(uB, prime)
    assert uA != uB
    assert uA < 0x100000000
    assert uB < 0x100000000


def test_dqn2int():
    assert dqn2int('255.255.255.0') == 24
    assert dqn2int('255.240.0.0') == 12
    assert dqn2int('255.0.0.0') == 8


def test_uifname():
    nA = uifname()
    nB = uifname()
    assert nA != nB
    assert int(nA[2:], 16) != int(nB[2:], 16)
