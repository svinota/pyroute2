from pr2modules.netlink import nlmsg


class rtgenmsg(nlmsg):

    fields = (('rtgen_family', 'B'), ('__pad', '3x'))
