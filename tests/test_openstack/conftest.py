import pytest

from pyroute2 import IPRoute, netns
from pyroute2.common import uifname


@pytest.fixture
def nsname(request, tmpdir):
    name = uifname()
    netns.create(name)
    yield name
    try:
        netns.remove(name)
    except:
        pass


@pytest.fixture
def link(request, tmpdir):
    name = uifname()
    with IPRoute() as ipr:
        ipr.link('add', ifname=name, kind='dummy', state='down')
        (link,) = ipr.link('get', ifname=name)
        yield link
        try:
            ipr.link('del', index=link['index'])
        except:
            pass
