from pyroute2.netlink.nfnetlink.nfctsocket import NFCTSocket


class Conntrack(NFCTSocket):
    """
    High level conntrack functions
    """

    def count(self):
        """ Return current number of conntrack entries

        Same result than /proc/sys/net/netfilter/nf_conntrack_count file
        or conntrack -C command
        """
        ndmsg = super(Conntrack, self).count()
        return ndmsg[0].get_attr('CTA_STATS_GLOBAL_ENTRIES')
