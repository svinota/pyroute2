import time
from utils import require_user
from pr2test.tools import interface_exists
from pyroute2 import config


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
    ifname1 = context.ifname
    ifname2 = context.ifname

    ndb = context.ndb

    #
    # the cache is empty from the beginning
    assert len(list(ndb.interfaces.cache)) == 0
    #
    # create test interfaces
    ndb.interfaces.create(ifname=ifname1, kind='dummy').commit()
    ndb.interfaces.create(ifname=ifname2, kind='dummy').commit()
    assert interface_exists(ifname=ifname1)
    assert interface_exists(ifname=ifname2)
    #
    # the interface object must not be cached, as they
    # weren't referenced yet
    assert len(list(ndb.interfaces.cache)) == 0
    #
    # setup the cache expiration time
    ce = config.cache_expire  # save the old value
    config.cache_expire = 1   # set the new one
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
    assert list(ndb
                .interfaces
                .cache
                .items())[0][1]['ifname'] == ifname2
    #
    # restore the environment
    config.cache_expire = ce
    ndb.interfaces[ifname1].remove().commit()
    ndb.interfaces[ifname2].remove().commit()

    #
    # check that the interfaces are cleaned up from the system
    assert not interface_exists(ifname=ifname1)
    assert not interface_exists(ifname=ifname2)
