from pyroute2 import NDB
from pyroute2.common import uifname


with NDB() as ndb:

    # dummy, bridge and bond interfaces are created in the
    # same way
    #
    # uifname() function is used here only to generate a
    # unique name of the interface for the regression testing,
    # you can pick up any name
    #
    ifname = uifname()
    (
        ndb.interfaces.create(kind='dummy', ifname=ifname, state='up')
        .set('state', 'up')
        .set('address', '00:11:22:33:44:55')
        .commit()
    )
    print(ndb.interfaces[ifname].show('json'))
    (
        ndb.interfaces[ifname]
        .remove()
        .commit()
    )
