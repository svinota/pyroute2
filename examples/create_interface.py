'''
Example: python ./examples/create_interface.py

Creates dummy interface.
'''
from pyroute2 import IPDB
from pyroute2.common import uifname

ip = IPDB()

try:

    # dummy, bridge and bond interfaces are created in the
    # same way
    #
    # uifname() function is used here only to generate a
    # unique name of the interface for the regression testing,
    # you can pick up any name
    #
    # details of this restriction are in the documentation
    #
    # possible kinds:
    #  * bond
    #  * bridge
    #  * dummy
    #  * vlan -- see /examples/create_vlan.py
    #
    dummy = ip.create(kind='dummy', ifname=uifname())
    dummy.commit()

finally:
    try:
        dummy.remove().commit()
    except:
        pass
    ip.release()
