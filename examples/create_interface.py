'''
Example: python ./examples/create_interface.py

Creates bond master interface.
'''
from pyroute2 import ipdb

ip = ipdb()

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
    bond = ip.create(kind='bond', ifname='bond,james')
    bond.commit()

finally:
    ip.shutdown()
