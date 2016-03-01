from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink import nla
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nfnetlink import nfgen_msg
from pyroute2.netlink.nfnetlink import NFNL_SUBSYS_NFTABLES

NFT_MSG_NEWTABLE = 0
NFT_MSG_GETTABLE = 1
NFT_MSG_DELTABLE = 2
NFT_MSG_NEWCHAIN = 3
NFT_MSG_GETCHAIN = 4
NFT_MSG_DELCHAIN = 5
NFT_MSG_NEWRULE = 6
NFT_MSG_GETRULE = 7
NFT_MSG_DELRULE = 8
NFT_MSG_NEWSET = 9
NFT_MSG_GETSET = 10
NFT_MSG_DELSET = 11
NFT_MSG_NEWSETELEM = 12
NFT_MSG_GETSETELEM = 13
NFT_MSG_DELSETELEM = 14
NFT_MSG_NEWGEN = 15
NFT_MSG_GETGEN = 16
NFT_MSG_TRACE = 17


class nft_gen_msg(nfgen_msg):
    nla_map = (('NFTA_GEN_UNSPEC', 'none'),
               ('NFTA_GEN_ID', 'be32'))


class nft_chain_msg(nfgen_msg):
    nla_map = (('NFTA_CHAIN_UNSPEC', 'none'),
               ('NFTA_CHAIN_TABLE', 'asciiz'),
               ('NFTA_CHAIN_HANDLE', 'be64'),
               ('NFTA_CHAIN_NAME', 'asciiz'),
               ('NFTA_CHAIN_HOOK', 'hook'),
               ('NFTA_CHAIN_POLICY', 'be32'),
               ('NFTA_CHAIN_USE',  'be32'),
               ('NFTA_CHAIN_TYPE', 'asciiz'),
               ('NFTA_CHAIN_COUNTERS', 'counters'))

    class counters(nla):
        nla_map = (('NFTA_COUNTER_UNSPEC', 'none'),
                   ('NFTA_COUNTER_BYTES', 'be64'),
                   ('NFTA_COUNTER_PACKETS', 'be64'))

    class hook(nla):
        nla_map = (('NFTA_HOOK_UNSPEC', 'none'),
                   ('NFTA_HOOK_HOOKNUM', 'be32'),
                   ('NFTA_HOOK_PRIORITY', 'be32'),
                   ('NFTA_HOOK_DEV', 'asciiz'))


class nft_rule_msg(nfgen_msg):
    nla_map = (('NFTA_RULE_UNSPEC', 'none'),
               ('NFTA_RULE_TABLE', 'asciiz'),
               ('NFTA_RULE_CHAIN', 'asciiz'),
               ('NFTA_RULE_HANDLE', 'be64'),
               ('NFTA_RULE_EXPRESSIONS', 'hex'),
               ('NFTA_RULE_COMPAT', 'hex'),
               ('NFTA_RULE_POSITION', 'be64'),
               ('NFTA_RULE_USERDATA', 'hex'))


class nft_set_msg(nfgen_msg):
    nla_map = (('NFTA_SET_UNSPEC', 'none'),
               ('NFTA_SET_TABLE', 'asciiz'),
               ('NFTA_SET_NAME', 'asciiz'),
               ('NFTA_SET_FLAGS', 'be32'),
               ('NFTA_SET_KEY_TYPE', 'be32'),
               ('NFTA_SET_KEY_LEN', 'be32'),
               ('NFTA_SET_DATA_TYPE', 'be32'),
               ('NFTA_SET_DATA_LEN', 'be32'),
               ('NFTA_SET_POLICY', 'be32'),
               ('NFTA_SET_DESC', 'hex'),
               ('NFTA_SET_ID', 'be32'),
               ('NFTA_SET_TIMEOUT', 'be32'),
               ('NFTA_SET_GC_INTERVAL', 'be32'),
               ('NFTA_SET_USERDATA', 'hex'))


class nft_table_msg(nfgen_msg):
    nla_map = (('NFTA_TABLE_UNSPEC', 'none'),
               ('NFTA_TABLE_NAME', 'asciiz'),
               ('NFTA_TABLE_FLAGS', 'be32'),
               ('NFTA_TABLE_USE', 'be32'))


class NFTSocket(NetlinkSocket):
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
        super(NFTSocket, self).__init__(family=NETLINK_NETFILTER)
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

    def get_tables(self):
        return self.request(nfgen_msg(), NFT_MSG_GETTABLE)

    def get_chains(self):
        return self.request(nfgen_msg(), NFT_MSG_GETCHAIN)

    def get_rules(self):
        return self.request(nfgen_msg(), NFT_MSG_GETRULE)

    def get_sets(self):
        return self.request(nfgen_msg(), NFT_MSG_GETSET)
