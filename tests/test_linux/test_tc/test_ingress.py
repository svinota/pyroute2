import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_simple(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'ingress', index=index)
    qdisc = None
    for qdisc in context.ipr.get_qdiscs(index=index):
        if qdisc.get_attr('TCA_KIND') == 'ingress':
            break
    else:
        raise FileNotFoundError('qdisc not found')
    assert qdisc['handle'] == 0xFFFF0000
    assert qdisc['parent'] == 0xFFFFFFF1
