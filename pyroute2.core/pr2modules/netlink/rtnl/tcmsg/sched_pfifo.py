from pr2modules.netlink import nla
from pr2modules.netlink.rtnl import TC_H_ROOT

parent = TC_H_ROOT


class options(nla):
    fields = (('limit', 'i'),)


def get_parameters(kwarg):
    return kwarg
