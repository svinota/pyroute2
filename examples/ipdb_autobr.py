'''
A sample of usage of IPDB generic callbacks
'''
from pyroute2 import IPDB
from pyroute2.common import uifname

# unique interface names -- for the testing
p0 = uifname()
br0 = uifname()


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
# More details read in pyroute2.ipdb
#
def cb(ipdb, msg, action):
    global p0
    global br0

    if action == 'RTM_NEWLINK' and \
            msg.get_attr('IFLA_IFNAME', '') == p0:
        # get corresponding interface -- in the case of
        # post-callbacks it is created already
        interface = ipdb.interfaces[msg['index']]
        # add it as a port to the bridge
        ipdb.interfaces[br0].add_port(interface)
        try:
            ipdb.interfaces[br0].commit()
        except Exception:
            pass


# create IPDB instance
with IPDB() as ip:
    # create watchdogs
    wd0 = ip.watchdog(ifname=br0)
    wd1 = ip.watchdog(ifname=p0)
    # create bridge
    ip.create(kind='bridge', ifname=br0).commit()
    # wait the bridge to be created
    wd0.wait()
    # register callback
    cuid = ip.register_callback(cb)
    # create ports
    ip.create(kind='dummy', ifname=p0).commit()
    # sleep for interfaces
    wd1.wait()

    ip.unregister_callback(cuid)

    # cleanup
    for i in (p0, br0):
        try:
            ip.interfaces[i].remove().commit()
        except:
            pass
