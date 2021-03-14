import os
import uuid
import time
import errno
import pytest
from utils import require_user
from test_tools import interface_exists
from pyroute2 import config
from pyroute2 import NDB
from pyroute2 import IPRoute
from pyroute2 import NetlinkError
from pyroute2.common import uifname


class ContextManager(object):
    '''
    This class is used to manage fixture contexts.

    * create log spec
    * create NDB with specified parameters
    * provide methods to register interfaces
    * automatically remove registered interfaces
    '''

    def __init__(self, **kwarg):
        # FIXME: use path provided by pytest, don't hardcode it
        log_id = str(uuid.uuid4())
        log_spec = '../ndb-%s-%s.log' % (os.getpid(), log_id)

        if 'log' not in kwarg:
            kwarg['log'] = log_spec
        if 'rtnl_debug' not in kwarg:
            kwarg['rtnl_debug'] = True
        #
        # this instance is to be tested, so do NOT use it
        # in utility methods
        self.ndb = NDB(**kwarg)
        self.ipr = IPRoute()
        self.interfaces = set()

    def register(self, ifname=None):
        '''
        Register an interface in `self.interfaces`. If no interface
        name specified, create a random one.

        All the saved interfaces will be removed on `teardown()`
        '''
        if ifname is None:
            ifname = uifname()
        self.interfaces.add(ifname)
        return ifname

    @property
    def ifname(self):
        '''
        The property `self.ifname` returns a new unique ifname and
        registers it to be cleaned up on `self.teardown()`
        '''
        return self.register()

    def teardown(self):
        '''
        1. close the test NDB
        2. remove the registered interfaces, ignore not existing
        3. close the IPRoute instance
        '''
        self.ndb.close()
        for ifname in self.interfaces:
            try:
                #
                # lookup the interface index
                index = list(self.ipr.link_lookup(ifname=ifname))
                if len(index):
                    index = index[0]
                else:
                    #
                    # ignore not existing interfaces
                    continue
                #
                # try to remove it
                self.ipr.link('del', index=index)
            except NetlinkError as e:
                #
                # ignore if removed (t.ex. by another process)
                if e.code != errno.ENODEV:
                    raise
        self.ipr.close()


@pytest.fixture
def local_ctx():
    '''
    This fixture is used to prepare the environment and
    to clean it up after each test.

    https://docs.pytest.org/en/stable/fixture.html
    '''
    #                      test stage:
    #
    ctx = ContextManager()  # setup
    yield ctx               # execute
    ctx.teardown()          # cleanup


class TestMisc(object):

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
        ndb.sources['localhost'].restart()
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

    def test_source_netns_restart(self):
        require_user('root')
        ifname = uifname()
        nsname = str(uuid.uuid4())

        with NDB() as ndb:
            ndb.sources.add(netns=nsname)
            assert len(list(ndb.interfaces.dump().filter(target=nsname)))
            ndb.sources[nsname].restart()
            assert len(list(ndb.interfaces.dump().filter(target=nsname)))
            (ndb
             .interfaces
             .create(target=nsname, ifname=ifname, kind='dummy', state='up')
             .commit())
            assert ndb.interfaces[{'target': nsname,
                                   'ifname': ifname}]['state'] == 'up'
            ndb.interfaces[{'target': nsname,
                            'ifname': ifname}].remove().commit()
