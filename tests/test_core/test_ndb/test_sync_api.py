import pytest

from pyroute2 import NDB


@pytest.mark.parametrize(
    'sequence,spec',
    (
        (
            (
                ('add_ip', (lambda n, x, s: s in x.ipaddr,)),
                ('ensure_ip', (lambda n, x, s: s in x.ipaddr,)),
                ('del_ip', (lambda n, x, s: s not in x.ipaddr,)),
                ('ensure_ip', (lambda n, x, s: s in x.ipaddr,)),
            ),
            {'address': '10.1.2.3', 'prefixlen': 24},
        ),
        (
            (
                ('add_neighbour', (lambda n, x, s: s in x.neighbours,)),
                ('ensure_neighbour', (lambda n, x, s: s in x.neighbours,)),
                ('del_neighbour', (lambda n, x, s: s not in x.neighbours,)),
                ('ensure_neighbour', (lambda n, x, s: s in x.neighbours,)),
            ),
            {'dst': '10.1.2.4', 'lladdr': '00:11:22:00:11:22'},
        ),
        (
            (
                ('add_port', (lambda n, x, s: s in x.ports,)),
                (
                    'del_port',
                    (
                        lambda n, x, s: s not in x.ports,
                        lambda n, x, s: s in n.interfaces,
                    ),
                ),
            ),
            {'ifname': '{test_link_ifname}'},
        ),
        (
            (
                (
                    'add_altname',
                    (lambda n, x, s: s['ifname'] in x['alt_ifname_list'],),
                ),
                (
                    'del_altname',
                    (lambda n, x, s: s['ifname'] not in x['alt_ifname_list'],),
                ),
            ),
            {'ifname': 'pr-altname42'},
        ),
    ),
    ids=('ipaddr', 'neighbour', 'vlan', 'altname'),
)
def test_interface_sequence(
    nsname, ndb, test_link_ifname, tmp_link_ifname, sequence, spec
):
    for key, value in tuple(spec.items()):
        if isinstance(value, str) and value[0] == '{' and value[-1] == '}':
            spec[key] = value.format(
                **{
                    'nsname': nsname,
                    'test_link_ifname': test_link_ifname,
                    'tmp_link_ifname': tmp_link_ifname,
                }
            )
    with NDB(sources=[{'target': 'localhost', 'netns': nsname}]) as test_ndb:
        ifname = tmp_link_ifname
        test_ndb.interfaces.create(
            ifname=ifname, kind='bridge', state='up'
        ).commit()
        for func_name, check_list in sequence:
            func = getattr(test_ndb.interfaces[ifname], func_name)
            func(**spec).commit()
            for check in check_list:
                assert check(ndb, ndb.interfaces[ifname], spec)
