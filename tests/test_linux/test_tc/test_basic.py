import errno

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import qdisc_exists

from pyroute2 import NetlinkError

pytestmark = [require_root()]
test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_pfifo(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'pfifo', index=index, limit=700)
    assert qdisc_exists(context.netns, 'pfifo', ifname=ifname, limit=700)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_pfifo_fast(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'pfifo_fast', index=index, handle=0)
    ret = qdisc_exists(context.netns, 'pfifo_fast', ifname=ifname)[0]
    assert ret.get_attr('TCA_OPTIONS')['priomap']


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_plug(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'plug', index=index, limit=13107)
    assert qdisc_exists(context.netns, 'plug', ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_blackhole(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'blackhole', index=index)
    assert qdisc_exists(context.netns, 'blackhole', ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_codel(context):
    index, ifname = context.default_interface
    context.ipr.tc(
        'add',
        'codel',
        index=index,
        handle='1:0',
        cdl_interval='40ms',
        cdl_target='2ms',
        cdl_limit=5000,
        cdl_ecn=1,
    )
    assert qdisc_exists(
        context.netns, 'codel', ifname=ifname, codel_ecn=1, codel_limit=5000
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_sfq(context):
    index, ifname = context.default_interface
    context.ipr.tc('add', 'sfq', index=index, handle=0, perturb=10)
    assert qdisc_exists(context.netns, 'sfq', ifname=ifname, perturb_period=10)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_tbf(context):
    index, ifname = context.default_interface
    context.ipr.tc(
        'add',
        'tbf',
        index=index,
        handle=0,
        rate='220kbit',
        latency='50ms',
        burst=1540,
    )
    opts = qdisc_exists(context.netns, 'tbf', ifname=ifname)[0].get_nested(
        'TCA_OPTIONS', 'TCA_TBF_PARMS'
    )
    assert opts['rate'] == 27500


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_choke(context):
    index, ifname = context.default_interface
    try:
        context.ipr.tc(
            'add', 'choke', index=index, limit=5500, bandwith=3000, ecn=True
        )
    except NetlinkError as e:
        if e.code == errno.ENOENT:
            pytest.skip('qdisc not supported: choke')
        raise
    opts = qdisc_exists(context.netns, 'choke', ifname=ifname)[0].get_nested(
        'TCA_OPTIONS', 'TCA_CHOKE_PARMS'
    )
    assert opts['limit'] == 5500
    assert opts['qth_max'] == 1375
    assert opts['qth_min'] == 458
