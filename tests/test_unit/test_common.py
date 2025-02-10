from pyroute2.common import dqn2int, uifname, uuid32


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
