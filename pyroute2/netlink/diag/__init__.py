from struct import pack
from socket import inet_ntop
from socket import AF_UNIX
from socket import AF_INET
from socket import AF_INET6
from socket import IPPROTO_TCP
from pyroute2.netlink import nlmsg
from pyroute2.netlink import nla
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

# multicast groups ids (for use with {add,drop}_membership)
SKNLGRP_NONE = 0
SKNLGRP_INET_TCP_DESTROY = 1
SKNLGRP_INET_UDP_DESTROY = 2
SKNLGRP_INET6_TCP_DESTROY = 3
SKNLGRP_INET6_UDP_DESTROY = 4


class sock_diag_req(nlmsg):

    fields = (('sdiag_family', 'B'),
              ('sdiag_protocol', 'B'))


UDIAG_SHOW_NAME = 0x01
UDIAG_SHOW_VFS = 0x02
UDIAG_SHOW_PEER = 0x04
UDIAG_SHOW_ICONS = 0x08
UDIAG_SHOW_RQLEN = 0x10
UDIAG_SHOW_MEMINFO = 0x20


class inet_addr_codec(nlmsg):

    def encode(self):
        # FIXME: add human-friendly API to specify IP addresses as str
        # (see also decode())
        if self['idiag_src'] == 0:
            self['idiag_src'] = (0, 0, 0, 0)
        if self['idiag_dst'] == 0:
            self['idiag_dst'] = (0, 0, 0, 0)
        nlmsg.encode(self)

    def decode(self):
        nlmsg.decode(self)
        current_familiy = self[self.ffname]
        if  current_familiy in [AF_INET, AF_INET6]:
            self['idiag_dst'] = inet_ntop(current_familiy,
                                          pack('>I', self['idiag_dst'][0]))
            self['idiag_src'] = inet_ntop(current_familiy,
                                          pack('>I', self['idiag_src'][0]))


class inet_diag_req(inet_addr_codec):

    ffname = 'sdiag_family'
    fields = (('sdiag_family', 'B'),
              ('sdiag_protocol', 'B'),
              ('idiag_ext', 'B'),
              ('__pad', 'B'),
              ('idiag_states', 'I'),
              ('idiag_sport', '>H'),
              ('idiag_dport', '>H'),
              ('idiag_src', '>4I'),
              ('idiag_dst', '>4I'),
              ('idiag_if', 'I'),
              ('idiag_cookie', 'Q'))


class inet_diag_msg(inet_addr_codec):

    ffname = 'idiag_family'
    fields = (('idiag_family', 'B'),
              ('idiag_state', 'B'),
              ('idiag_timer', 'B'),
              ('idiag_retrans', 'B'),
              ('idiag_sport', '>H'),
              ('idiag_dport', '>H'),
              ('idiag_src', '>4I'),
              ('idiag_dst', '>4I'),
              ('idiag_if', 'I'),
              ('idiag_cookie', 'Q'),
              ('idiag_expires', 'I'),
              ('idiag_rqueue', 'I'),
              ('idiag_wqueue', 'I'),
              ('idiag_uid', 'I'),
              ('idiag_inode', 'I'))

    class inet_diag_meminfo(nla):
        fields = (('idiag_rmem', 'I'),
                  ('idiag_wmem', 'I'),
                  ('idiag_fmem', 'I'),
                  ('idiag_tmem', 'I')
                 )


class tcp_inet_diag_msg(inet_diag_msg):

    nla_map = (('INET_DIAG_NONE', 'none'),
               ('INET_DIAG_MEMINFO', 'inet_diag_meminfo'),
               ('INET_DIAG_INFO', 'tcp_info'),
               ('INET_DIAG_VEGASINFO', 'tcpvegas_info'),
               ('INET_DIAG_CONG', 'asciiz'),
               ('INET_DIAG_TOS', 'hex'),
               ('INET_DIAG_TCLASS', 'hex'),
               ('INET_DIAG_SKMEMINFO', 'hex'),
               ('INET_DIAG_SHUTDOWN', 'uint8'),
               ('INET_DIAG_DCTCPINFO', 'hex'),
               ('INET_DIAG_PROTOCOL', 'hex'),
               ('INET_DIAG_SKV6ONLY', 'hex'),
               ('INET_DIAG_LOCALS', 'hex'),
               ('INET_DIAG_PEERS', 'hex'),
               ('INET_DIAG_PAD', 'hex'),
               ('INET_DIAG_MARK', 'hex'),
               ('INET_DIAG_BBRINFO', 'hex'),
               ('INET_DIAG_CLASS_ID', 'hex'),
               ('INET_DIAG_MD5SIG', 'hex'))

    class tcp_info(nla):
        fields = (('tcpi_state', 'B'),
                  ('tcpi_ca_state', 'B'),
                  ('tcpi_retransmits', 'B'),
                  ('tcpi_probes', 'B'),
                  ('tcpi_backoff', 'B'),
                  ('tcpi_options', 'B'),
                  ('tcpi_wscale', 'B'),
                  ('tcpi_rto', 'I'),
                  ('tcpi_ato', 'I'),
                  ('tcpi_snd_mss', 'I'),
                  ('tcpi_rcv_mss', 'I'),
                  ('tcpi_unacked', 'I'),
                  ('tcpi_sacked', 'I'),
                  ('tcpi_lost', 'I'),
                  ('tcpi_retrans', 'I'),
                  ('tcpi_fackets', 'I'),
                  ('tcpi_last_data_sent', 'I'),
                  ('tcpi_last_ack_sent', 'I'),
                  ('tcpi_last_data_recv', 'I'),
                  ('tcpi_last_ack_recv', 'I'),
                  ('tcpi_pmtu', 'I'),
                  ('tcpi_rcv_ssthresh', 'I'),
                  ('tcpi_rtt', 'I'),
                  ('tcpi_rttvar', 'I'),
                  ('tcpi_snd_ssthresh', 'I'),
                  ('tcpi_snd_cwnd', 'I'),
                  ('tcpi_advmss', 'I'),
                  ('tcpi_reordering', 'I'),
                  ('tcpi_rcv_rtt', 'I'),
                  ('tcpi_rcv_space', 'I'),
                  ('tcpi_total_retrans', 'I'))

    class tcpvegas_info(nla):
        fields = (('tcpv_enabled', 'I'),
                  ('tcpv_rttcnt',  'I'),
                  ('tcpv_rtt',     'I'),
                  ('tcpv_minrtt',  'I')
                 )




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

    nla_map = (('UNIX_DIAG_NAME', 'asciiz'),
               ('UNIX_DIAG_VFS', 'unix_diag_vfs'),
               ('UNIX_DIAG_PEER', 'uint32'),
               ('UNIX_DIAG_ICONS', 'hex'),
               ('UNIX_DIAG_RQLEN', 'unix_diag_rqlen'),
               ('UNIX_DIAG_MEMINFO', 'hex'),
               ('UNIX_DIAG_SHUTDOWN', 'uint8'))

    class unix_diag_vfs(nla):
        fields = (('udiag_vfs_ino', 'I'),
                  ('udiag_vfs_dev', 'I'))

    class unix_diag_rqlen(nla):
        fields = (('udiag_rqueue', 'I'),
                  ('udiag_wqueue', 'I'))


class MarshalDiag(Marshal):
    type_format = 'B'
    # The family goes after the nlmsg header,
    # IHHII = 4 + 2 + 2 + 4 + 4 = 16 bytes
    type_offset = 16
    # Please notice that the SOCK_DIAG Marshal
    # uses not the nlmsg type, but sdiag_family
    # to choose the proper class
    msg_map = {AF_UNIX: unix_diag_msg,
               # set prot specific 
               AF_INET: None}
    # error type NLMSG_ERROR == 2 == AF_INET,
    # it doesn't work for DiagSocket that way,
    # so disable the error messages for now
    error_type = -1

    def adapt(self, protocol):
        if protocol == IPPROTO_TCP:
            self.msg_map[AF_INET] = tcp_inet_diag_msg


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
                       protocol=IPPROTO_TCP,
                       extensions=0,
                       show=(UDIAG_SHOW_NAME |
                             UDIAG_SHOW_VFS |
                             UDIAG_SHOW_PEER |
                             UDIAG_SHOW_ICONS)):
        '''
        Get sockets statistics.

        ACHTUNG: the get_sock_stats() signature will be changed
        before the next release, this one is a WIP-code!
        '''

        if family == AF_UNIX:
            req = unix_diag_req()
            req['udiag_states'] = states
            req['udiag_show'] = show
        elif family == AF_INET or family == AF_INET6:
            req = inet_diag_req()
            req['idiag_states'] = states
            req['sdiag_protocol'] = protocol
            req['idiag_ext'] = extensions
            self.marshal.adapt(protocol)
        else:
            raise NotImplementedError()
        req['sdiag_family'] = family

        return self.nlm_request(req, SOCK_DIAG_BY_FAMILY,
                                NLM_F_REQUEST | NLM_F_ROOT | NLM_F_MATCH)
