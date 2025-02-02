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
def test_brport_set(ipr, ndb, link, param, value):
    brname = uifname()
    ndb.interfaces.create(ifname=brname, kind='bridge').add_port(
        link.get('ifname')
    ).commit()
    kwarg = {param: value}
    ipr.brport('set', index=link.get('index'), **kwarg)
    ipr.poll(ipr.brport, 'dump', index=link.get('index'), timeout=5, **kwarg)
