import time
import pytest
from utils import require_user
from pr2test.tools import interface_exists
from pr2test.ctx_managers import NDBContextManager
from pyroute2 import config
from pyroute2 import NDB


@pytest.fixture
def local_ctx(tmpdir):
    '''
    This fixture is used to prepare the environment and
    to clean it up after each test.

    https://docs.pytest.org/en/stable/fixture.html
    '''
    #                              test stage:
    #
    ctx = NDBContextManager(tmpdir)  # setup
    yield ctx                        # execute
    ctx.teardown()                   # cleanup


class TestSources(object):

    def test_multiple_sources(self):
        '''
        NDB should work with multiple netlink sources

        Check that it actually works:
        * with multiple sources of different kind
        * without the default "localhost" RTNL source
        '''

        #
        # NB: no 'localhost' record -- important !
        sources = [{'target': 'localhost0', 'kind': 'local'},
                   {'target': 'localhost1', 'kind': 'remote'},
                   {'target': 'localhost2', 'kind': 'remote'}]
        ndb = None
        #
        # check that all the view has length > 0
        # that means that the sources are working
        with NDB(sources=sources) as ndb:
            assert len(list(ndb.interfaces.dump()))
            assert len(list(ndb.neighbours.dump()))
            assert len(list(ndb.addresses.dump()))
            assert len(list(ndb.routes.dump()))
        # here NDB() gets closed
        #

        #
        # the `ndb` variable still references the closed
        # NDB() object from the code block above, check
        # that all the sources are closed too
        for source in ndb.sources:
            assert ndb.sources[source].nl.closed

    def test_source_localhost_restart(self, local_ctx):
        '''
        The database must be operational after a complete
        restart of any source.
        '''
        require_user('root')
        ifname1 = local_ctx.ifname
        ifname2 = local_ctx.ifname
        ndb = local_ctx.ndb

        #
        # check that there are existing interfaces
        # loaded into the DB
        assert len(list(ndb.interfaces.dump()))
        #
        # create a dummy interface to prove the
        # source working
        (ndb
         .interfaces
         .create(ifname=ifname1, kind='dummy', state='up')
         .commit())
        #
        # an external check
        assert interface_exists(ifname1, state='up')
        #
        # internal checks
        assert ifname1 in ndb.interfaces
        assert ndb.interfaces[ifname1]['state'] == 'up'
        #
        # now restart the source
        # the reason should be visible in the log
        ndb.sources['localhost'].restart(reason='test')
        #
        # the interface must be in the DB (after the
        # source restart)
        assert ifname1 in ndb.interfaces
        #
        # create another one
        (ndb
         .interfaces
         .create(ifname=ifname2, kind='dummy', state='down')
         .commit())
        #
        # check the interface both externally and internally
        assert interface_exists(ifname2, state='down')
        assert ifname2 in ndb.interfaces
        assert ndb.interfaces[ifname2]['state'] == 'down'
        #
        # cleanup
        ndb.interfaces[ifname1].remove().commit()
        ndb.interfaces[ifname2].remove().commit()
        #
        # check
        assert not interface_exists(ifname1)
        assert not interface_exists(ifname2)

    def test_source_netns_restart(self, local_ctx):
        '''
        Netns sources should be operational after restart as well
        '''
        require_user('root')
        nsname = local_ctx.nsname
        #
        # simple `local_ctx.ifname` returns ifname only for the main
        # netns, if we want to register the name in a netns, we should
        # use `local_ctx.register(netns=...)`
        ifname = local_ctx.register(netns=nsname)
        ndb = local_ctx.ndb

        #
        # add a netns source, the netns will be created automatically
        ndb.sources.add(netns=nsname)
        #
        # check the interfaces from the netns are loaded into the DB
        assert len(list(ndb.interfaces.dump().filter(target=nsname)))
        #
        # restart the DB
        ndb.sources[nsname].restart(reason='test')
        #
        # check the netns interfaces again
        assert len(list(ndb.interfaces.dump().filter(target=nsname)))
        #
        # create an interface in the netns
        (ndb
         .interfaces
         .create(target=nsname, ifname=ifname, kind='dummy', state='up')
         .commit())
        #
        # check the interface
        assert interface_exists(ifname, nsname)
        assert ndb.interfaces[{'target': nsname,
                               'ifname': ifname}]['state'] == 'up'
        #
        # netns will be remove automatically by the fixture as well
        # as interfaces inside the netns


class TestViewCache(object):

    def test_view_cache(self, local_ctx):
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
        ifname1 = local_ctx.ifname
        ifname2 = local_ctx.ifname

        ndb = local_ctx.ndb

        #
        # the cache is empty from the beginning
        assert len(list(ndb.interfaces.cache)) == 0
        #
        # create test interfaces
        ndb.interfaces.create(ifname=ifname1, kind='dummy').commit()
        ndb.interfaces.create(ifname=ifname2, kind='dummy').commit()
        assert interface_exists(ifname1)
        assert interface_exists(ifname2)
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
        assert not interface_exists(ifname1)
        assert not interface_exists(ifname2)
