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


class nft_map_uint8(nla):
    ops = {}
    fields = [('value', 'B')]

    def decode(self):
        nla.decode(self)
        self.value = self.ops.get(self['value'])


class nft_map_be32(nft_map_uint8):
    fields = [('value', '>I')]


class nft_regs(nla):
    class regs(nft_map_be32):
        ops = {0x00: 'NFT_REG_VERDICT',
               0x01: 'NFT_REG_1',
               0x02: 'NFT_REG_2',
               0x03: 'NFT_REG_3',
               0x04: 'NFT_REG_4',
               0x08: 'NFT_REG32_00',
               0x09: 'MFT_REG32_01',
               0x0a: 'NFT_REG32_02',
               0x0b: 'NFT_REG32_03',
               0x0c: 'NFT_REG32_04',
               0x0d: 'NFT_REG32_05',
               0x0e: 'NFT_REG32_06',
               0x0f: 'NFT_REG32_07',
               0x10: 'NFT_REG32_08',
               0x11: 'NFT_REG32_09',
               0x12: 'NFT_REG32_10',
               0x13: 'NFT_REG32_11',
               0x14: 'NFT_REG32_12',
               0x15: 'NFT_REG32_13',
               0x16: 'NFT_REG32_14',
               0x17: 'NFT_REG32_15'}


class nft_data(nla):
    class data(nla):
        nla_map = (('NFTA_DATA_UNSPEC', 'none'),
                   ('NFTA_DATA_VALUE', 'cdata'),
                   ('NFTA_DATA_VERDICT', 'verdict'))

        class verdict(nla):
            nla_map = (('NFTA_VERDICT_UNSPEC', 'none'),
                       ('NFTA_VERDICT_CODE', 'be32'),
                       ('NFTA_VERDICT_CHAIN', 'asciiz'))


class nft_rule_msg(nfgen_msg):
    nla_map = (('NFTA_RULE_UNSPEC', 'none'),
               ('NFTA_RULE_TABLE', 'asciiz'),
               ('NFTA_RULE_CHAIN', 'asciiz'),
               ('NFTA_RULE_HANDLE', 'be64'),
               ('NFTA_RULE_EXPRESSIONS', '*rule_expr'),
               ('NFTA_RULE_COMPAT', 'hex'),
               ('NFTA_RULE_POSITION', 'be64'),
               ('NFTA_RULE_USERDATA', 'hex'))

    class rule_expr(nla):
        nla_map = (('NFTA_EXPR_UNSPEC', 'none'),
                   ('NFTA_EXPR_NAME', 'asciiz'),
                   ('NFTA_EXPR_DATA', 'expr'))

        class nft_bitwise(nft_data, nft_regs):
            nla_map = (('NFTA_BITWISE_UNSPEC', 'none'),
                       ('NFTA_BITWISE_SREG', 'regs'),
                       ('NFTA_BITWISE_DREG', 'regs'),
                       ('NFTA_BITWISE_LEN', 'be32'),
                       ('NFTA_BITWISE_MASK', 'data'),
                       ('NFTA_BITWISE_XOR', 'data'))

        class nft_byteorder(nft_regs):
            nla_map = (('NFTA_BYTEORDER_UNSPEC', 'none'),
                       ('NFTA_BYTEORDER_SREG', 'regs'),
                       ('NFTA_BYTEORDER_DREG', 'regs'),
                       ('NFTA_BYTEORDER_OP', 'ops'),
                       ('NFTA_BYTEORDER_LEN', 'be32'),
                       ('NFTA_BYTEORDER_SIZE', 'be32'))

            class ops(nft_map_be32):
                ops = {0: 'NFT_BYTEORDER_NTOH',
                       1: 'NFT_BYTEORDER_HTON'}

        class nft_cmp(nft_data, nft_regs):
            nla_map = (('NFTA_CMP_UNSPEC', 'none'),
                       ('NFTA_CMP_SREG', 'regs'),
                       ('NFTA_CMP_OP', 'ops'),
                       ('NFTA_CMP_DATA', 'data'))

            class ops(nft_map_be32):
                ops = {0: 'NFT_CMP_EQ',
                       1: 'NFT_CMP_NEQ',
                       2: 'NFT_CMP_LT',
                       3: 'NFT_CMP_LTE',
                       4: 'NFT_CMP_GT',
                       5: 'NFT_CMP_GTE'}

        class nft_counter(nla):
            nla_map = (('NFTA_COUNTER_UNSPEC', 'none'),
                       ('NFTA_COUNTER_BYTES', 'be64'),
                       ('NFTA_COUNTER_PACKETS', 'be64'))

        class nft_ct(nft_regs):
            nla_map = (('NFTA_CT_UNSPEC', 'none'),
                       ('NFTA_CT_DREG', 'regs'),
                       ('NFTA_CT_KEY', 'keys'),
                       ('NFTA_CT_DIRECTION', 'uint8'),
                       ('NFTA_CT_SREG', 'regs'))

            class keys(nft_map_be32):
                ops = {0x00: 'NFT_CT_STATE',
                       0x01: 'NFT_CT_DIRECTION',
                       0x02: 'NFT_CT_STATUS',
                       0x03: 'NFT_CT_MARK',
                       0x04: 'NFT_CT_SECMARK',
                       0x05: 'NFT_CT_EXPIRATION',
                       0x06: 'NFT_CT_HELPER',
                       0x07: 'NFT_CT_L3PROTOCOL',
                       0x08: 'NFT_CT_SRC',
                       0x09: 'NFT_CT_DST',
                       0x0a: 'NFT_CT_PROTOCOL',
                       0x0b: 'NFT_CT_PROTO_SRC',
                       0x0c: 'NFT_CT_PROTO_DST',
                       0x0d: 'NFT_CT_LABELS',
                       0x0e: 'NFT_CT_PKTS',
                       0x0f: 'NFT_CT_BYTES'}

        class nft_exthdr(nft_regs):
            nla_map = (('NFTA_EXTHDR_UNSPEC', 'none'),
                       ('NFTA_EXTHDR_DREG', 'regs'),
                       ('NFTA_EXTHDR_TYPE', 'uint8'),
                       ('NFTA_EXTHDR_OFFSET', 'be32'),
                       ('NFTA_EXTHDR_LEN', 'be32'))

        class nft_immediate(nft_data, nft_regs):
            nla_map = (('NFTA_IMMEDIATE_UNSPEC', 'none'),
                       ('NFTA_IMMEDIATE_DREG', 'regs'),
                       ('NFTA_IMMEDIATE_DATA', 'data'))

        class nft_limit(nla):
            nla_map = (('NFTA_LIMIT_UNSPEC', 'none'),
                       ('NFTA_LIMIT_RATE', 'be64'),
                       ('NFTA_LIMIT_UNIT', 'be64'),
                       ('NFTA_LIMIT_BURST', 'be32'),
                       ('NFTA_LIMIT_TYPE', 'types'),
                       ('NFTA_LIMIT_FLAGS', 'be32'))  # make flags type

            class types(nft_map_be32):
                ops = {0: 'NFT_LIMIT_PKTS',
                       1: 'NFT_LIMIT_PKT_BYTES'}

        class nft_log(nla):
            nla_map = (('NFTA_LOG_UNSPEC', 'none'),
                       ('NFTA_LOG_GROUP', 'be32'),
                       ('NFTA_LOG_PREFIX', 'asciiz'),
                       ('NFTA_LOG_SNAPLEN', 'be32'),
                       ('NFTA_LOG_QTHRESHOLD', 'be32'),
                       ('NFTA_LOG_LEVEL', 'be32'),
                       ('NFTA_LOG_FLAGS', 'be32'))

        class nft_lookup(nft_regs):
            nla_map = (('NFTA_LOOKUP_UNSPEC', 'none'),
                       ('NFTA_LOOKUP_SET', 'asciiz'),
                       ('NFTA_LOOKUP_SREG', 'regs'),
                       ('NFTA_LOOKUP_DREG', 'regs'),
                       ('NFTA_LOOKUP_SET_ID', 'be32'))

        class nft_masq(nla):
            nla_map = (('NFTA_MASQ_UNSPEC', 'none'),
                       ('NFTA_MASQ_FLAGS', 'be32'))

        class nft_meta(nft_regs):
            nla_map = (('NFTA_META_UNSPEC', 'none'),
                       ('NFTA_META_DREG', 'regs'),
                       ('NFTA_META_KEY', 'be32'),
                       ('NFTA_META_SREG', 'regs'))

        class nft_nat(nft_regs):
            nla_map = (('NFTA_NAT_UNSPEC', 'none'),
                       ('NFTA_NAT_TYPE', 'types'),
                       ('NFTA_NAT_FAMILY', 'be32'),
                       ('NFTA_NAT_REG_ADDR_MIN', 'regs'),
                       ('NFTA_NAT_REG_ADDR_MAX', 'regs'),
                       ('NFTA_NAT_REG_PROTO_MIN', 'regs'),
                       ('NFTA_NAT_REG_PROTO_MAX', 'regs'),
                       ('NFTA_NAT_FLAGS', 'be32'))

            class types(nft_map_be32):
                ops = {0: 'NFT_NAT_SNAT',
                       1: 'NFT_NAT_DNAT'}

        class nft_payload(nft_regs):
            nla_map = (('NFTA_PAYLOAD_UNSPEC', 'none'),
                       ('NFTA_PAYLOAD_DREG', 'regs'),
                       ('NFTA_PAYLOAD_BASE', 'base_type'),
                       ('NFTA_PAYLOAD_OFFSET', 'be32'),
                       ('NFTA_PAYLOAD_LEN', 'be32'),
                       ('NFTA_PAYLOAD_SREG', 'regs'),
                       ('NFTA_PAYLOAD_CSUM_TYPE', 'csum_type'),
                       ('NFTA_PAYLOAD_CSUM_OFFSET', 'be32'))

            class base_type(nft_map_be32):
                ops = {0: 'NFT_PAYLOAD_LL_HEADER',
                       1: 'NFT_PAYLOAD_NETWORK_HEADER',
                       2: 'NFT_PAYLOAD_TRANSPORT_HEADER'}

            class csum_type(nft_map_be32):
                ops = {0: 'NFT_PAYLOAD_CSUM_NONE',
                       1: 'NFT_PAYLOAD_CSUM_INET'}  # RFC 791

        class nft_queue(nla):
            nla_map = (('NFTA_QUEUE_UNSPEC', 'none'),
                       ('NFTA_QUEUE_NUM', 'be16'),
                       ('NFTA_QUEUE_TOTAL', 'be16'),
                       ('NFTA_QUEUE_FLAGS', 'be16'))

        class nft_redir(nft_regs):
            nla_map = (('NFTA_REDIR_UNSPEC', 'none'),
                       ('NFTA_REDIR_REG_PROTO_MIN', 'regs'),
                       ('NFTA_REDIR_REG_PROTO_MAX', 'regs'),
                       ('NFTA_REDIR_FLAGS', 'be32'))

        class nft_reject(nla):
            nla_map = (('NFTA_REJECT_UNSPEC', 'none'),
                       ('NFTA_REJECT_TYPE', 'types'),
                       ('NFTA_REJECT_ICMP_CODE', 'codes'))

            class types(nft_map_be32):
                ops = {0: 'NFT_REJECT_ICMP_UNREACH',
                       1: 'NFT_REJECT_TCP_RST',
                       2: 'NFT_REJECT_ICMPX_UNREACH'}

            class codes(nft_map_uint8):
                ops = {0: 'NFT_REJECT_ICMPX_NO_ROUTE',
                       1: 'NFT_REJECT_ICMPX_PORT_UNREACH',
                       2: 'NFT_REJECT_ICMPX_HOST_UNREACH',
                       3: 'NFT_REJECT_ICMPX_ADMIN_PROHIBITED'}

        @staticmethod
        def expr(self, *argv, **kwarg):
            data_type = self.get_attr('NFTA_EXPR_NAME')
            return getattr(self, 'nft_%s' % data_type, self.hex)


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
