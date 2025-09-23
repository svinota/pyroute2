from pyroute2.common import dqn2int, map_namespace, uifname, uuid32


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


def test_map_namespace():
    others = {
        'IFNAMSIZ': 16,
        '__name__': 'pyroute2.bsd.pf_route.freebsd',
        '__doc__': None,
    }
    prefixed = {'IFF_UP': 1, 'IFF_NOGROUP': 8388608}
    prefixed_by_value = {1: 'IFF_UP', 8388608: 'IFF_NOGROUP'}
    ns = prefixed | others

    by_name, by_value = map_namespace('IFF', ns)

    assert by_name == prefixed
    assert by_value == prefixed_by_value


def test_map_namespace_normalize():
    others = {
        'IFNAMSIZ': 16,
        '__name__': 'pyroute2.bsd.pf_route.freebsd',
        '__doc__': None,
    }
    prefixed = {'IFF_UP': 1, 'IFF_NOGROUP': 8388608}
    normalized = {'_up': 1, '_nogroup': 8388608}
    normalized_by_value = {1: '_up', 8388608: '_nogroup'}
    ns = prefixed | others

    by_name, by_value = map_namespace('IFF', ns, True)

    assert by_name == normalized
    assert by_value == normalized_by_value


def test_map_namespace_normalize_function():
    def normalizer(s: str) -> str:
        return s.removeprefix('IFF_')

    others = {
        'IFNAMSIZ': 16,
        '__name__': 'pyroute2.bsd.pf_route.freebsd',
        '__doc__': None,
    }
    prefixed = {'IFF_UP': 1, 'IFF_NOGROUP': 8388608}
    normalized = {'UP': 1, 'NOGROUP': 8388608}
    normalized_by_value = {1: 'UP', 8388608: 'NOGROUP'}
    ns = prefixed | others

    by_name, by_value = map_namespace('IFF', ns, normalizer)

    assert by_name == normalized
    assert by_value == normalized_by_value
