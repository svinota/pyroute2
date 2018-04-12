from pyroute2.netlink.nfnetlink.nfctsocket import NFCTSocket


class Conntrack(NFCTSocket):
    """
    High level conntrack functions
    """

    def stat(self):
        """ Return current statistics per CPU

        Same result than conntrack -S command but a list of dictionaries
        """
        stats = []

        for msg in super(Conntrack, self).stat():
            stats.append({'cpu': msg['res_id']})
            stats[-1].update((k[10:].lower(), v) for k, v in msg['attrs']
                             if k.startswith('CTA_STATS_'))

        return stats

    def count(self):
        """ Return current number of conntrack entries

        Same result than /proc/sys/net/netfilter/nf_conntrack_count file
        or conntrack -C command
        """
        ndmsg = super(Conntrack, self).count()
        return ndmsg[0].get_attr('CTA_STATS_GLOBAL_ENTRIES')
