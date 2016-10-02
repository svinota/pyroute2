from socket import AF_UNIX
from pyroute2.netlink import nlmsg
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_ROOT
from pyroute2.netlink import NLM_F_MATCH
from pyroute2.netlink import NETLINK_SOCK_DIAG
from pyroute2.netlink.nlsocket import Marshal
from pyroute2.netlink.nlsocket import NetlinkSocket

SOCK_DIAG_BY_FAMILY = 20
SOCK_DESTROY = 21


class sock_diag_req(nlmsg):

    fields = (('sdiag_family', 'B'),
              ('sdiag_protocol', 'B'))

UDIAG_SHOW_NAME = 0x01
UDIAG_SHOW_VFS = 0x02
UDIAG_SHOW_PEER = 0x04
UDIAG_SHOW_ICONS = 0x08
UDIAG_SHOW_RQLEN = 0x10
UDIAG_SHOW_MEMINFO = 0x20


class unix_diag_req(nlmsg):

    fields = (('sdiag_family', 'B'),
              ('sdiag_protocol', 'B'),
              ('__pad', 'H'),
              ('udiag_states', 'I'),
              ('udiag_ino', 'I'),
              ('udiag_show', 'I'),
              ('udiag_cookie', 'Q'))


class unix_diag_msg(nlmsg):

    fields = (('udiag_family', 'B'),
              ('udiag_type', 'B'),
              ('udiag_state', 'B'),
              ('__pad', 'B'),
              ('udiag_ino', 'I'),
              ('udiag_cookie', 'Q'))


class MarshalDiag(Marshal):
    type_format = 'B'
    # The family goes after the nlmsg header,
    # IHHII = 4 + 2 + 2 + 4 + 4 = 16 bytes
    type_offset = 16
    # Please notice that the SOCK_DIAG Marshal
    # uses not the nlmsg type, but sdiag_family
    # to choose the proper class
    msg_map = {AF_UNIX: unix_diag_msg}


class DiagSocket(NetlinkSocket):

    def __init__(self, fileno=None):
        super(DiagSocket, self).__init__(NETLINK_SOCK_DIAG)
        self.marshal = MarshalDiag()

    def test(self):
        '''
        This function is here only as an example and for
        debugging purposes. It will be removed in the release.

        Usage::

            from pprint import pprint
            from pyroute2.netlink.diag import DiagSocket
            ds = DiagSocket()
            ds.bind()
            pprint(ds.test())

        '''

        req = unix_diag_req()
        req['sdiag_family'] = AF_UNIX
        req['udiag_states'] = 0xb37
        req['udiag_show'] = UDIAG_SHOW_NAME |\
            UDIAG_SHOW_VFS |\
            UDIAG_SHOW_PEER |\
            UDIAG_SHOW_ICONS

        return self.nlm_request(req, SOCK_DIAG_BY_FAMILY,
                                NLM_F_REQUEST | NLM_F_ROOT | NLM_F_MATCH)
