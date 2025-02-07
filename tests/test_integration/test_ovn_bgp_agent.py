import pytest

from pyroute2 import iproute
from pyroute2.common import uifname


@pytest.mark.parametrize(
    'method,argv',
    (('get_rules', []), ('route', ['show']), ('brport', ['show'])),
)
def test_iproute_call(method, argv):
    with iproute.IPRoute() as ip:
        iter(getattr(ip, method)(*argv))


@pytest.mark.parametrize(
    'param,value', (('neigh_suppress', True), ('learning', False))
)
def test_brport_set(
    sync_ipr, ndb, test_link_index, test_link_ifname, param, value
):
    brname = uifname()
    ndb.interfaces.create(ifname=brname, kind='bridge').add_port(
        test_link_ifname
    ).commit()
    kwarg = {param: value}
    sync_ipr.brport('set', index=test_link_index, **kwarg)
    sync_ipr.poll(
        sync_ipr.brport, 'dump', index=test_link_index, timeout=5, **kwarg
    )
