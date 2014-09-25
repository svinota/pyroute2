from pyroute2.netlink import CTRL_CMD_GETFAMILY
from pyroute2.netlink import GENL_ID_CTRL
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import ctrlmsg
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nlsocket import Marshal


class GenericNetlinkSocket(NetlinkSocket):

    def bind(self, proto, msg_class, groups=0, pid=0):
        NetlinkSocket.bind(self, groups, pid)
        self.marshal.msg_map[GENL_ID_CTRL] = ctrlmsg
        self.prid = self.get_protocol_id(proto)
        self.marshal.msg_map[self.prid] = msg_class

    def get_protocol_id(self, prid):
        msg = ctrlmsg()
        msg['cmd'] = CTRL_CMD_GETFAMILY
        msg['version'] = 1
        msg['attrs'].append(['CTRL_ATTR_FAMILY_NAME', prid])
        msg['header']['type'] = GENL_ID_CTRL
        msg['header']['flags'] = NLM_F_REQUEST
        msg['header']['pid'] = self.pid
        msg.encode()
        self.sendto(msg.buf.getvalue(), (0, 0))
        msg = self.get()[0]
        return msg.get_attr('CTRL_ATTR_FAMILY_ID')
