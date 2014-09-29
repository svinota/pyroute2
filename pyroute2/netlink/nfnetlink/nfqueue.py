from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink import nlmsg
from pyroute2.netlink import nla
from pyroute2.netlink.client import Netlink
from pyroute2.netlink.nlsocket import Marshal

NFNL_SUBSYS_NONE = 0
NFNL_SUBSYS_CTNETLINK = 1
NFNL_SUBSYS_CTNETLINK_EXP = 2
NFNL_SUBSYS_QUEUE = 3
NFNL_SUBSYS_ULOG = 4
NFNL_SUBSYS_OSF = 5
NFNL_SUBSYS_IPSET = 6
NFNL_SUBSYS_COUNT = 7

# constants
NFQNL_MSG_PACKET = 0
NFQNL_MSG_VERDICT = 1
NFQNL_MSG_CONFIG = 2

# verdict types
NF_DROP = 0
NF_ACCEPT = 1
NF_STOLEN = 2
NF_QUEUE = 3
NF_REPEAT = 4
NF_STOP = 5


class nfq_packet_msg(nlmsg):
    pass


class nfq_verdict_msg(nlmsg):
    pass


class nfq_config_msg(nlmsg):
    nla_map = (('NFQA_CFG_UNSPEC', 'none'),
               ('NFQA_CFG_CMD', 'nfqa_cfg_cmd'),
               ('NFQA_CFG_PARAMS', 'none'))

    class nfqa_cfg_cmd(nla):
        fields = (('command', 'B'),
                  ('__pad', '1x'),
                  ('pf', 'H'))


class MarshalNFQ(Marshal):

    msg_map = {NFQNL_MSG_PACKET: nfq_packet_msg,
               NFQNL_MSG_VERDICT: nfq_verdict_msg,
               NFQNL_MSG_CONFIG: nfq_config_msg}


class NFQ(Netlink):

    family = NETLINK_NETFILTER
    marshal = MarshalNFQ

    def __init__(self):
        Netlink.__init__(self, pid=0)

    def config(self):
        msg = nfq_config_msg()
        msg['header']['flags'] = NLM_F_REQUEST
        msg['header']['type'] = (3 << 8) | NFQNL_MSG_CONFIG
        msg['attrs'] = [['NFQA_CFG_CMD', {'command': 1,
                                          'pf': 1}]]
        msg.encode()
        self.push(msg.buf.getvalue())
