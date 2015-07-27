from pprint import pprint
from pyroute2 import IPDB
from pyroute2.common import uifname

ip = IPDB(debug=True)

# create an interface
i = ip.create(kind='dummy', ifname=uifname()).commit()
prev_state = i.nlmsg

# change the state
i.address = '00:11:22:33:44:55'
i.up()
i.commit()

# show, what has been changed, excluding statistics --
# it changes all the time
pprint((i.nlmsg - prev_state).strip(('IFLA_AF_SPEC',
                                     'IFLA_STATS',
                                     'IFLA_STATS64',
                                     'IFLA_LINKINFO',
                                     'IFLA_MAP')))

i.remove().commit()

ip.release()
