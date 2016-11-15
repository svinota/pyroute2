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

# states
SS_UNKNOWN = 0
SS_ESTABLISHED = 1
SS_SYN_SENT = 2
SS_SYN_RECV = 3
SS_FIN_WAIT1 = 4
SS_FIN_WAIT2 = 5
SS_TIME_WAIT = 6
SS_CLOSE = 7
SS_CLOSE_WAIT = 8
SS_LAST_ACK = 9
SS_LISTEN = 10
SS_CLOSING = 11
SS_MAX = 12

SS_ALL = ((1 << SS_MAX) - 1)
SS_CONN = (SS_ALL & ~((1 << SS_LISTEN) |
                      (1 << SS_CLOSE) |
                      (1 << SS_TIME_WAIT) |
                      (1 << SS_SYN_RECV)))


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
    '''
    Usage::

        from pyroute2 import DiagSocket
        with DiagSocket() as ds:
            ds.bind()
            sstats = ds.get_sock_stats()

    '''

    def __init__(self, fileno=None):
        super(DiagSocket, self).__init__(NETLINK_SOCK_DIAG)
        self.marshal = MarshalDiag()

    def get_sock_stats(self,
                       family=AF_UNIX,
                       states=SS_ALL,
                       show=(UDIAG_SHOW_NAME |
                             UDIAG_SHOW_VFS |
                             UDIAG_SHOW_PEER |
                             UDIAG_SHOW_ICONS)):
        '''
        Get sockets statistics.
        '''

        if family == AF_UNIX:
            req = unix_diag_req()
        else:
            raise NotImplementedError()
        req['sdiag_family'] = family
        req['udiag_states'] = states
        req['udiag_show'] = show

        return self.nlm_request(req, SOCK_DIAG_BY_FAMILY,
                                NLM_F_REQUEST | NLM_F_ROOT | NLM_F_MATCH)
