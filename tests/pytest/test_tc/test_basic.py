import pytest
from pr2test.tools import qdisc_exists
from pr2test.context_manager import make_test_matrix

test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_qdisc_pfifo(context):
    ifname = context.new_ifname
    ipr = context.ipr

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .commit())

    ipr.tc('add',
           'pfifo',
           index=context.ndb.interfaces[ifname]['index'],
           limit=700)

    assert qdisc_exists(context.netns, 'pfifo', ifname=ifname, limit=700)
