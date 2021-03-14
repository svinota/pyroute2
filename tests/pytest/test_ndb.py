import os
import uuid
import time
from utils import require_user
from test_tools import interface_exists
from pyroute2 import config
from pyroute2 import NDB
from pyroute2.common import uifname


class TestMisc(object):

    def test_view_cache(self):
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
        log_id = str(uuid.uuid4())
        ifname1 = uifname()
        ifname2 = uifname()
        #
        # using `whith` means that the NDB() object will be
        # closed after the statement exits
        with NDB(log='../ndb-%s-%s.log' % (os.getpid(), log_id),
                 rtnl_debug=True) as ndb:
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

    def test_source_localhost_restart(self):
        '''
        '''
        require_user('root')
        ifname = uifname()

        with NDB() as ndb:
            assert len(list(ndb.interfaces.dump()))
            ndb.sources['localhost'].restart()
            assert len(list(ndb.interfaces.dump()))
            (ndb
             .interfaces
             .create(ifname=ifname, kind='dummy', state='up')
             .commit())
            assert ndb.interfaces[ifname]['state'] == 'up'
            ndb.interfaces[ifname].remove().commit()

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
