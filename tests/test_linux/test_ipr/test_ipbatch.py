from pr2test.marks import require_root

from pyroute2 import IPBatch

pytestmark = [require_root()]


def test_link_add(context):

    ifname = context.new_ifname

    ipb = IPBatch()
    ipb.link('add', ifname=ifname, kind='dummy')
    data = ipb.batch
    ipb.reset()
    ipb.close()
    context.ipr.sendto(data, (0, 0))
    context.ndb.interfaces.wait(ifname=ifname, timeout=3)
