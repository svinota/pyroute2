from pyroute2 import netns
from pyroute2.netlink.rtnl.ifinfmsg.tuntap import manage_tun, manage_tuntap

IFNAMSIZ = 16


def proxy_newlink(msg, nsname, channel):
    kind = msg.get(('linkinfo', 'kind'))
    ret = b''
    if nsname is not None:
        netns.setns(nsname)
    if kind == 'tuntap':
        ret = manage_tuntap(msg)
    if kind == 'tun':
        ret = manage_tun(msg)
    channel.put(ret)
