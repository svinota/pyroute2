import struct
from socket import AF_ROUTE
from socket import SOCK_RAW
from pyroute2 import config
from pyroute2.bsd.pf_route import (if_msg,
                                   rt_msg,
                                   if_announcemsg,
                                   ifma_msg,
                                   ifa_msg)

RTM_ADD = 0x1          # Add Route
RTM_DELETE = 0x2       # Delete Route
RTM_CHANGE = 0x3       # Change Metrics or flags
RTM_GET = 0x4          # Report Metrics
RTM_LOSING = 0x5       # Kernel Suspects Partitioning
RTM_REDIRECT = 0x6     # Told to use different route
RTM_MISS = 0x7         # Lookup failed on this address
RTM_LOCK = 0x8         # Fix specified metrics
RTM_RESOLVE = 0xb      # Req to resolve dst to LL addr
RTM_NEWADDR = 0xc      # Address being added to iface
RTM_DELADDR = 0xd      # Address being removed from iface
RTM_IFINFO = 0xe       # Iface going up/down etc
RTM_NEWMADDR = 0xf     # Mcast group membership being added to if
RTM_DELMADDR = 0x10    # Mcast group membership being deleted
RTM_IFANNOUNCE = 0x11  # Iface arrival/departure
RTM_IEEE80211 = 0x12   # IEEE80211 wireless event


class RTMSocket(object):

    msg_map = {RTM_ADD: rt_msg,
               RTM_DELETE: rt_msg,
               RTM_CHANGE: rt_msg,
               RTM_GET: rt_msg,
               RTM_LOSING: rt_msg,
               RTM_REDIRECT: rt_msg,
               RTM_MISS: rt_msg,
               RTM_LOCK: rt_msg,
               RTM_RESOLVE: rt_msg,
               RTM_NEWADDR: ifa_msg,
               RTM_DELADDR: ifa_msg,
               RTM_IFINFO: if_msg,
               RTM_NEWMADDR: ifma_msg,
               RTM_DELMADDR: ifma_msg,
               RTM_IFANNOUNCE: if_announcemsg,
               RTM_IEEE80211: if_announcemsg}

    def __init__(self):
        self._sock = config.SocketBase(AF_ROUTE, SOCK_RAW)

    def get(self):
        msg = self._sock.recv(2048)
        _, _, msg_type = struct.unpack('HBB', msg[:4])
        msg_class = self.msg_map.get(msg_type, None)
        if msg_class is not None:
            msg = msg_class(msg)
            msg.decode()
        return msg
