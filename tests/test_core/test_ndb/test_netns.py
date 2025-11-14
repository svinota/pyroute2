from pyroute2 import NDB
from pyroute2.common import uifname


def test_intefaces_setns(nsname, ndb):
    '''Bug-Url: https://github.com/svinota/pyroute2/issues/1439'''
    ifname = uifname()
    with NDB() as ndb_main:
        ndb_main.sources.add(netns=nsname)
        ndb_main.interfaces.create(ifname=ifname, kind='dummy').commit()
        ndb_main.interfaces[ifname].set('target', nsname).commit()
        assert ifname in ndb.interfaces


def test_intefaces_setlocalns(nsname, test_link_ifname, ndb):
    '''Bug-Url: https://github.com/svinota/pyroute2/issues/1439'''
    with NDB() as ndb_main:
        ndb_main.sources.add(netns=nsname)
        ndb_main.interfaces[
            {'target': nsname, 'ifname': test_link_ifname}
        ].set('target', 'localhost').commit()
    with NDB() as ndb_main:
        assert test_link_ifname in ndb_main.interfaces
        ndb_main.interfaces[test_link_ifname].remove().commit()


def test_multiple_there_and_back(nsname, ndb, cleanup):
    '''Bug-Url: https://github.com/svinota/pyroute2/issues/1442'''

    netns0 = uifname()
    netns1 = uifname()
    cleanup.netns.add(netns0)
    cleanup.netns.add(netns1)
    ndb.sources.add(netns=netns0)
    ndb.sources.add(netns=netns1)

    ndb.interfaces.create(ifname="p0", kind="veth", peer="p1").commit()
    (
        ndb.interfaces[{"target": "localhost", "ifname": "p0"}]
        .set("target", netns0)
        .commit()
    )
    (
        ndb.interfaces[{"target": "localhost", "ifname": "p1"}]
        .set("target", netns1)
        .commit()
    )

    (
        ndb.interfaces[{"target": netns0, "ifname": "p0"}]
        .add_ip("172.16.1.1/24")
        .set('state', 'up')
        .commit()
    )
    (
        ndb.interfaces[{"target": netns1, "ifname": "p1"}]
        .add_ip("172.16.1.2/24")
        .set('state', 'up')
        .commit()
    )

    (
        ndb.interfaces[{"target": netns0, "ifname": "p0"}]
        .set("state", "down")
        .del_ip("172.16.1.1/24")
        .commit()
    )
    (
        ndb.interfaces[{"target": netns1, "ifname": "p1"}]
        .set("state", "down")
        .del_ip("172.16.1.2/24")
        .commit()
    )
    (
        ndb.interfaces[{"target": netns1, "ifname": "p1"}]
        .set("target", "localhost")
        .commit()
    )

    returned = (
        ndb.interfaces[{"target": netns0, "ifname": "p0"}]
        .set("target", "localhost")
        .commit()
    )
    lookup = ndb.interfaces[{"ifname": "p0"}]
    assert returned['target'] == lookup['target']
    ndb.interfaces[{"target": "localhost", "ifname": "p0"}].remove().commit()
