'''
A sample of usage of IPDB generic callbacks
'''
from pyroute2 import IPDB


###
#
# The callback receives three arguments:
# 1. ipdb reference
# 2. msg arrived
# 3. action (actually, that's msg['event'] field)
#
# By default, callbacks are registered as 'post',
# it means that they're executed after any other
# action on a message arrival.
#
# More details read in pyroute2/netlink/ipdb.py
#
def cb(ipdb, msg, action):
    if action == 'RTM_NEWLINK' and \
            msg.get_attr('IFLA_IFNAME', '').startswith('bala_port'):
        with ipdb.exclusive:
            # get corresponding interface -- in the case of
            # post-callbacks it is created already
            interface = ipdb.interfaces[msg['index']]
            # add it as a port to the bridge
            ipdb.interfaces.br0.add_port(interface)
            ipdb.interfaces.br0.commit()

# create IPDB instance
ip = IPDB()
# create bridge
ip.create(kind='bridge', ifname='br0').commit()
# wait the bridge to be created
ip.wait_interface(ifname='br0')
# register callback
ip.register_callback(cb)
# create ports
ip.create(kind='dummy', ifname='bala_port0').commit()
ip.create(kind='dummy', ifname='bala_port1').commit()
# sleep for interfaces
ip.wait_interface(ifname='bala_port0')
ip.wait_interface(ifname='bala_port1')
input(" >> ")
ip.release()
