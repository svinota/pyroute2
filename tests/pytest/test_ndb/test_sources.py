from utils import require_user
from pr2test.tools import interface_exists
from pyroute2 import NDB


def test_multiple_sources():
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


def test_source_localhost_restart(context):
    '''
    The database must be operational after a complete
    restart of any source.
    '''
    require_user('root')
    ifname1 = context.ifname
    ifname2 = context.ifname
    ndb = context.ndb

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


def test_source_netns_restart(context):
    '''
    Netns sources should be operational after restart as well
    '''
    require_user('root')
    nsname = context.nsname
    #
    # simple `context.ifname` returns ifname only for the main
    # netns, if we want to register the name in a netns, we should
    # use `context.register(netns=...)`
    ifname = context.register(netns=nsname)
    ndb = context.ndb

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


def count_interfaces(ndb, target):
    return (ndb
            .schema
            .fetchone('''
                      SELECT count(*) FROM interfaces
                      WHERE
                          f_target = '%s' AND
                          f_index != 0
                      ''' % target))[0]


def test_disconnect_localhost(context):
    '''
    Disconnecting the `localhost` source should not break the DB
    '''
    require_user('root')
    nsname = context.nsname
    localhost_ifnum = 0
    nsname_ifnum = 0
    total_ifnum = 0

    #
    # attach the NetNS source
    context.ndb.sources.add(netns=nsname)

    #
    # lock the DB
    with context.ndb.readonly:
        total_ifnum = (context
                       .ndb
                       .interfaces
                       .dump()
                       .count())
        localhost_ifnum = (context
                           .ndb
                           .interfaces
                           .dump()
                           .filter(target='localhost')
                           .count())
        nsname_ifnum = (context
                        .ndb
                        .interfaces
                        .dump()
                        .filter(target=nsname)
                        .count())

        assert localhost_ifnum == count_interfaces(context.ndb, 'localhost')
        assert nsname_ifnum == count_interfaces(context.ndb, nsname)
        assert 0 < count_interfaces(context.ndb, 'localhost') < total_ifnum
        assert 0 < count_interfaces(context.ndb, nsname) < total_ifnum

    context.ndb.sources.remove('localhost')

    with context.ndb.readonly:
        #
        # the number of 'localhost' interfaces must be 0 here
        s = len(list(context
                     .ndb
                     .interfaces
                     .dump()
                     .filter(target='localhost')))
        assert s == 0
        assert count_interfaces(context.ndb, 'localhost') == 0
        #
        # the number of `nsname` interfaces must remain the same as before
        s = len(list(context
                     .ndb
                     .interfaces
                     .dump()
                     .filter(target=nsname)))
        assert s > 0
        assert count_interfaces(context.ndb, nsname) == s
