import pytest
from socket import AF_INET6
from pr2test.tools import rule_exists
from pr2test.context_manager import make_test_matrix

test_matrix = make_test_matrix(
    targets=['local', 'netns'],
    tables=[100, 10000],
    dbs=['sqlite3/:memory:', 'postgres/pr2test'],
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_explicit_ipv6_src(context):
    ipnet = context.new_ip6net
    table = context.table

    spec = {
        'family': AF_INET6,
        'src': ipnet.network,
        'src_len': ipnet.netmask,
        'table': table,
        'priority': 50,
    }
    context.register_rule(spec)

    context.ndb.rules.create(**spec).commit()
    assert rule_exists(context.netns, **spec)

    context.ndb.rules[spec].remove().commit()
    assert not rule_exists(context.netns, **spec)
