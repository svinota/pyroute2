from pyroute2.netlink.rtnl import TC_H_CLSACT

parent = TC_H_CLSACT


def fix_msg(msg, kwarg):
    msg['handle'] = 0xffff0000
