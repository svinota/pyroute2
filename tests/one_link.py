from pyroute2 import iproute
from pprint import pprint
from pyroute2.netlink.rtmsg.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl import RTM_GETLINK
from socket import AF_UNSPEC

ip = iproute(debug=True)
pprint(ip.nlm_request(ifinfmsg, RTM_GETLINK,
       msg_family=AF_UNSPEC, msg_flags=1, msg_fields={'index': 1}))
