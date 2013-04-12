from pyroute2.iproute import iproute
from pprint import pprint
from pyroute2.netlink.rtmsg.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl import RTM_GETLINK

ip = iproute(debug=True)
pprint(ip.nlm_request(ifinfmsg, RTM_GETLINK, msg_flags=1 | 0x100 | 0x200))
# pprint(ip.nlm_request(ifinfmsg, RTM_GETLINK,
# msg_family=AF_BRIDGE, msg_flags=1, msg_fields={'index': 4}))
