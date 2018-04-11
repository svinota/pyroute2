from pyroute2.netlink import \
    (NLM_F_REQUEST,
     NLM_F_DUMP)
from pyroute2.netlink.nfnetlink.nfctsocket import \
    (NFCTSocket,
     nfct_stats,
     IPCTNL_MSG_CT_GET_STATS)


def terminate_single_msg(msg):
    return msg


class Conntrack(NFCTSocket):
    """
    High level conntrack functions
    """

    def count(self):
        """ Return current number of conntrack entries

        Same result than /proc/sys/net/netfilter/nf_conntrack_count file
        or conntrack -C command
        """
        msg = nfct_stats()

        ndmsg = self.request(msg, IPCTNL_MSG_CT_GET_STATS,
                             msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
                             terminate=terminate_single_msg)
        return ndmsg[0].get_attr('CTA_STATS_GLOBAL_ENTRIES')
