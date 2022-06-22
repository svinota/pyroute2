import time
from functools import partial

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import interface_exists
from utils import require_user

from pyroute2 import config

pytestmark = [require_root()]

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_view_cache(context):
    '''
    NDB stores all the info in an SQL database, and instantiates
    python objects only upon request, since it isn't cheap.
    References to the created objects are stored in the object
    cache until expired.

    This test checks is the cache works as expected. Initially
    there should be no references in the cache, check if the
    references are properly cached and expired in time.
    '''
    require_user('root')
    ifname1 = context.new_ifname
    ifname2 = context.new_ifname

    ndb = context.ndb

    #
    # the cache is empty from the beginning
    assert len(list(ndb.interfaces.cache)) == 0
    #
    # create test interfaces
    ndb.interfaces.create(ifname=ifname1, kind='dummy').commit()
    ndb.interfaces.create(ifname=ifname2, kind='dummy').commit()
    assert interface_exists(context.netns, ifname=ifname1)
    assert interface_exists(context.netns, ifname=ifname2)
    #
    # the interface object must not be cached, as they
    # weren't referenced yet
    assert len(list(ndb.interfaces.cache)) == 0
    #
    # setup the cache expiration time
    ce = config.cache_expire  # save the old value
    config.cache_expire = 1  # set the new one
    #
    # access the interfaces via __getitem__() -- this must
    # create objects and cache the references
    assert ndb.interfaces[ifname1] is not None
    assert ndb.interfaces[ifname2] is not None
    #
    # both references must be in the cache now
    assert len(list(ndb.interfaces.cache)) == 2
    #
    # expire the cache
    time.sleep(1)
    #
    # access the second interface to trigger the
    # cache invalidation
    assert ndb.interfaces[ifname2] is not None
    #
    # ifname1 must be out of the cache now as not
    # accessed within the timeout
    #
    # only ifname2 must remain
    assert len(list(ndb.interfaces.cache)) == 1
    assert list(ndb.interfaces.cache.items())[0][1]['ifname'] == ifname2
    #
    # restore the environment
    config.cache_expire = ce
    ndb.interfaces[ifname1].remove().commit()
    ndb.interfaces[ifname2].remove().commit()

    #
    # check that the interfaces are cleaned up from the system
    assert not interface_exists(context.netns, ifname=ifname1)
    assert not interface_exists(context.netns, ifname=ifname2)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_readonly(context):
    readonly = context.ndb.readonly()

    with pytest.raises(PermissionError):
        readonly.interfaces.create(ifname='test', kind='dummy')

    selection = list(readonly.interfaces.summary().filter(ifname='lo'))
    assert len(selection) == 1
    assert selection[0].ifname == 'lo'
    assert selection[0].address == '00:00:00:00:00:00'
    assert selection[0].target == 'localhost'


@pytest.mark.parametrize('method', ('dump', 'summary'))
@pytest.mark.parametrize(
    'view,sub,func',
    (
        ('routes', 'routes', lambda index, x: x.oif == index),
        ('addresses', 'ipaddr', lambda index, x: x.index == index),
        ('interfaces', 'ports', lambda index, x: x.master == index),
        ('neighbours', 'neighbours', lambda index, x: x.ifindex == index),
        ('vlans', 'vlans', lambda index, x: x.index == index),
    ),
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_nested_count(context, view, sub, func, method):
    br0 = context.new_ifname
    br0p0 = context.new_ifname
    br0p1 = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    gateway = context.new_ipaddr
    net = context.new_ip4net

    context.ndb.interfaces.create(
        ifname=br0p0, kind='dummy', state='up'
    ).commit()
    context.ndb.interfaces.create(
        ifname=br0p1, kind='dummy', state='up'
    ).commit()
    (
        context.ndb.interfaces.create(ifname=br0, kind='bridge', state='up')
        .add_port(br0p0)
        .add_port(br0p1)
        .add_ip(f'{ipaddr1}/24')
        .add_ip(f'{ipaddr2}/24')
        .commit()
    )
    context.ndb.routes.create(
        dst=net.network, dst_len=net.netmask, gateway=gateway
    ).commit()

    records_a = (
        getattr(context.ndb, view)
        .dump()
        .filter(partial(func, context.ndb.interfaces[br0]['index']))
    )
    records_b = getattr(getattr(context.ndb.interfaces[br0], sub), method)()
    count = getattr(context.ndb.interfaces[br0], sub).count()
    assert records_b.count() == records_a.count() == count
    assert count < getattr(context.ndb, view).count() or count == 0
