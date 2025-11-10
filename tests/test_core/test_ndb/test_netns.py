from pyroute2 import NDB
from pyroute2.common import uifname


def test_intefaces_setns(nsname, ndb):
    ifname = uifname()
    with NDB() as ndb_main:
        ndb_main.sources.add(netns=nsname)
        ndb_main.interfaces.create(ifname=ifname, kind='dummy').commit()
        ndb_main.interfaces[ifname].set('target', nsname).commit()
        assert ifname in ndb.interfaces


def test_intefaces_setlocalns(nsname, test_link_ifname, ndb):
    with NDB() as ndb_main:
        ndb_main.sources.add(netns=nsname)
        ndb_main.interfaces[
            {'target': nsname, 'ifname': test_link_ifname}
        ].set('target', 'localhost').commit()
    with NDB() as ndb_main:
        assert test_link_ifname in ndb_main.interfaces
        ndb_main.interfaces[test_link_ifname].remove().commit()
