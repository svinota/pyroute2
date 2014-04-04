'''
Example of "pre" callback
'''
from pyroute2 import IPDB


###
#
# "Pre" callbacks are executed before the message
# gets processed by IPDB, and in synchronous manner.
# Normally, you will not need these callbacks, but
# they can be useful to perform some hacks
#
def cb(ipdb, msg, action):
    if action == 'RTM_NEWLINK':
        msg['flags'] = 1234

# create IPDB instance
ip = IPDB()
# register "pre" callback
ip.register_callback(cb, mode='pre')
# create an interface
ip.create(kind='dummy', ifname='bala').commit()
# assert flags
print(ip.interfaces.bala.flags)
# cleanup
ip.interfaces.bala.remove()
ip.interfaces.bala.commit()
# release Netlink socket
ip.release()
