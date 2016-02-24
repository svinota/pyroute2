'''
'''
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nfnetlink import NFNL_SUBSYS_NFTABLES

from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_NEWTABLE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_GETTABLE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_DELTABLE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_NEWCHAIN
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_GETCHAIN
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_DELCHAIN
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_NEWRULE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_GETRULE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_DELRULE
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_NEWSET
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_GETSET
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_DELSET
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_NEWGEN
from pyroute2.netlink.nfnetlink.nftables import NFT_MSG_GETGEN

from pyroute2.netlink.nfnetlink.nftables import nft_table_msg
from pyroute2.netlink.nfnetlink.nftables import nft_chain_msg
from pyroute2.netlink.nfnetlink.nftables import nft_rule_msg
from pyroute2.netlink.nfnetlink.nftables import nft_set_msg
from pyroute2.netlink.nfnetlink.nftables import nft_gen_msg


def _nlmsg_error(msg):
    return msg['header']['type'] == NLMSG_ERROR


class NFTables(NetlinkSocket):
    '''
    NFNetlink socket (family=NETLINK_NETFILTER).

    Implements API to the nftables functionality.
    '''
    policy = {NFT_MSG_NEWTABLE: nft_table_msg,
              NFT_MSG_GETTABLE: nft_table_msg,
              NFT_MSG_DELTABLE: nft_table_msg,
              NFT_MSG_NEWCHAIN: nft_chain_msg,
              NFT_MSG_GETCHAIN: nft_chain_msg,
              NFT_MSG_DELCHAIN: nft_chain_msg,
              NFT_MSG_NEWRULE: nft_rule_msg,
              NFT_MSG_GETRULE: nft_rule_msg,
              NFT_MSG_DELRULE: nft_rule_msg,
              NFT_MSG_NEWSET: nft_set_msg,
              NFT_MSG_GETSET: nft_set_msg,
              NFT_MSG_DELSET: nft_set_msg,
              NFT_MSG_NEWGEN: nft_gen_msg,
              NFT_MSG_GETGEN: nft_gen_msg}

    def __init__(self, version=1, attr_revision=0, nfgen_family=2):
        super(NFTables, self).__init__(family=NETLINK_NETFILTER)
        policy = dict([(x | (NFNL_SUBSYS_NFTABLES << 8), y)
                       for (x, y) in self.policy.items()])
        self.register_policy(policy)
        self._proto_version = version
        self._attr_revision = attr_revision
        self._nfgen_family = nfgen_family

    def request(self, msg, msg_type,
                msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
                terminate=None):
        msg['nfgen_family'] = self._nfgen_family
        return self.nlm_request(msg,
                                msg_type | (NFNL_SUBSYS_NFTABLES << 8),
                                msg_flags, terminate=terminate)
