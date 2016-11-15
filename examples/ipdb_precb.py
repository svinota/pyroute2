'''
Example of "pre" callback
'''
from pyroute2 import IPDB
from pyroute2.common import uifname

p0 = uifname()


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
ip.create(kind='dummy', ifname=p0).commit()
# assert flags
assert ip.interfaces[p0].flags == 1234
# cleanup
ip.interfaces[p0].remove()
ip.interfaces[p0].commit()
# release Netlink socket
ip.release()
