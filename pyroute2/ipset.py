import socket
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_EXCL
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nfnetlink import NFNL_SUBSYS_IPSET
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_PROTOCOL
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_CREATE
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_DESTROY
from pyroute2.netlink.nfnetlink.ipset import IPSET_CMD_LIST
from pyroute2.netlink.nfnetlink.ipset import ipset_msg


class IPSet(NetlinkSocket):

    policy = {IPSET_CMD_PROTOCOL: ipset_msg,
              IPSET_CMD_LIST: ipset_msg}

    def __init__(self, version=6, attr_revision=2, nfgen_family=2):
        super(IPSet, self).__init__(family=NETLINK_NETFILTER)
        policy = dict([(x | (NFNL_SUBSYS_IPSET << 8), y)
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
                                msg_type | (NFNL_SUBSYS_IPSET << 8),
                                msg_flags, terminate=terminate)

    def list(self, name=None):
        '''
        List installed ipsets. If `name` is provided, list
        the named ipset or return an empty list.

        It looks like nfnetlink doesn't return an error,
        when requested ipset doesn't exist.
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version]]
        if name is not None:
            msg['attrs'].append(['IPSET_ATTR_SETNAME', name])
        return self.request(msg, IPSET_CMD_LIST)

    def delete(self, name):
        '''
        Remove an ipset
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', name]]
        return self.request(msg, IPSET_CMD_DESTROY,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK | NLM_F_EXCL,
                            terminate=lambda x: x['header']['type'] ==
                            NLMSG_ERROR)

    def create(self, name, stype='hash:ip', family=socket.AF_INET):
        '''
        Create an ipset `name` of type `stype`, by default
        `hash:ip`.

        Very simple and stupid method, should be extended
        to support ipset options.
        '''
        msg = ipset_msg()
        msg['attrs'] = [['IPSET_ATTR_PROTOCOL', self._proto_version],
                        ['IPSET_ATTR_SETNAME', name],
                        ['IPSET_ATTR_TYPENAME', stype],
                        ['IPSET_ATTR_FAMILY', family],
                        ['IPSET_ATTR_REVISION', self._attr_revision]]

        return self.request(msg, IPSET_CMD_CREATE,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK | NLM_F_EXCL,
                            terminate=lambda x: x['header']['type'] ==
                            NLMSG_ERROR)
