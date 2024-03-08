from pyroute2.netlink import NLM_F_ACK, NLM_F_DUMP, NLM_F_REQUEST, genlmsg
from pyroute2.netlink.generic import GenericNetlinkSocket

GENL_NAME = "IPVS"
GENL_VERSION = 0x1

IPVS_CMD_UNSPEC = 0

IPVS_CMD_NEW_SERVICE = 1
IPVS_CMD_SET_SERVICE = 2
IPVS_CMD_DEL_SERVICE = 3
IPVS_CMD_GET_SERVICE = 4

IPVS_CMD_NEW_DEST = 5
IPVS_CMD_SET_DEST = 6
IPVS_CMD_DEL_DEST = 7
IPVS_CMD_GET_DEST = 8

IPVS_CMD_NEW_DAEMON = 9
IPVS_CMD_DEL_DAEMON = 10
IPVS_CMD_GET_DAEMON = 11

IPVS_CMD_SET_CONFIG = 12
IPVS_CMD_GET_CONFIG = 13

IPVS_CMD_SET_INFO = 14
IPVS_CMD_GET_INFO = 15

IPVS_CMD_ZERO = 16
IPVS_CMD_FLUSH = 17


class ipvsmsg(genlmsg):
    prefix = "IPVS_CMD_ATTR_"
    nla_map = (
        ("IPVS_CMD_ATTR_UNSPEC", "none"),
        ("IPVS_CMD_ATTR_SERVICE", "hex"),
        ("IPVS_CMD_ATTR_DEST", "hex"),
        ("IPVS_CMD_ATTR_DAEMON", "hex"),
        ("IPVS_CMD_ATTR_TIMEOUT_TCP", "hex"),
        ("IPVS_CMD_ATTR_TIMEOUT_TCP_FIN", "hex"),
        ("IPVS_CMD_ATTR_TIMEOUT_UDP", "hex"),
    )


class IPVSSocket(GenericNetlinkSocket):
    def __init__(self, *argv, **kwargs):
        super().__init__(*argv, **kwargs)
        self.bind(GENL_NAME, ipvsmsg)

    def service(self, cmd):
        msg = ipvsmsg()
        msg["cmd"] = cmd
        msg["version"] = GENL_VERSION
        return self.nlm_request(
            msg,
            msg_type=self.prid,
            msg_flags=NLM_F_REQUEST | NLM_F_ACK | NLM_F_DUMP,
        )
