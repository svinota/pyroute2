import errno

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import qdisc_exists

from pyroute2 import NetlinkError

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_drr(context):
    index, ifname = context.default_interface
    try:
        context.ipr.tc('add', 'drr', index=index, handle='1:')
    except NetlinkError as e:
        if e.code == errno.ENOENT:
            pytest.skip('qdisc not supported: drr')
        raise
    context.ipr.tc('add-class', 'drr', index=index, handle='1:20', quantum=20)
    context.ipr.tc('add-class', 'drr', index=index, handle='1:30', quantum=30)
    assert qdisc_exists(context.netns, 'drr', ifname=ifname)
    cls = context.ipr.get_classes(index=index)
    assert len(cls) == 2
    assert cls[0].get_attr('TCA_KIND') == 'drr'
    assert cls[1].get_attr('TCA_KIND') == 'drr'
    assert cls[0].get_attr('TCA_OPTIONS').get_attr('TCA_DRR_QUANTUM') == 20
    assert cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_DRR_QUANTUM') == 30


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_hfsc(context):
    index, ifname = context.default_interface
    # root queue
    context.ipr.tc('add', 'hfsc', index=index, handle='1:0', default='1:1')
    assert qdisc_exists(context.netns, 'hfsc', ifname=ifname, defcls=1)
    # classes
    context.ipr.tc(
        'add-class',
        'hfsc',
        index=index,
        handle='1:1',
        parent='1:0',
        rsc={'m2': '3mbit'},
    )
    cls = context.ipr.get_classes(index=index)
    assert len(cls) == 2  # implicit root class + the defined one
    assert cls[0].get_attr('TCA_KIND') == 'hfsc'
    assert cls[1].get_attr('TCA_KIND') == 'hfsc'
    curve = cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_RSC')
    assert curve['m1'] == 0
    assert curve['d'] == 0
    assert curve['m2'] == 375000
    assert cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_FSC') is None
    assert cls[1].get_attr('TCA_OPTIONS').get_attr('TCA_HFSC_USC') is None
