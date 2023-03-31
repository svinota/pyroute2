import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import interface_exists

pytestmark = [require_root()]

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_altname_complex(context):
    index, ifname = context.default_interface
    altname1 = context.new_ifname
    altname2 = context.new_ifname
    with context.ndb.interfaces[ifname] as i:
        i.add_altname(altname1)

    assert interface_exists(context.netns, altname=altname1)
    assert not interface_exists(context.netns, altname=altname2)

    with context.ndb.interfaces[ifname] as i:
        i.del_altname(altname1)
        i.add_altname(altname2)

    assert interface_exists(context.netns, altname=altname2)
    assert not interface_exists(context.netns, altname=altname1)

    with context.ndb.interfaces[ifname] as i:
        i.del_altname(altname2)

    assert not interface_exists(context.netns, altname=altname1)
    assert not interface_exists(context.netns, altname=altname2)
