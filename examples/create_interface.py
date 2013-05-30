'''
Example: python ./examples/create_interface.py

Creates dummy interface.
'''
from pyroute2 import IPDB

ip = IPDB()

try:

    # dummy, bridge and bond interfaces are created in the
    # same way -- just use appropriate name
    #
    # Warning! do not use name 'bond0'
    # Warning! do not use name 'dummy0'
    # details of this restriction are in the documentation
    #
    # possible kinds:
    #  * bond
    #  * bridge
    #  * dummy
    #  * vlan -- see /examples/create_vlan.py
    #
    bond = ip.create(kind='dummy', ifname='dummy_name')
    bond.commit()

finally:
    ip.release()
