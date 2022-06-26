import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import qdisc_exists

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_qdisc_pfifo(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'pfifo', index=index, limit=700)
    assert qdisc_exists(context.netns, 'pfifo', ifname=ifname, limit=700)
