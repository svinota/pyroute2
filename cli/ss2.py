#!/usr/bin/env python
# pyroute2 - ss2
#Copyright (C) 2018  Matthias Tafelmeier

#ss2 is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#ss2 is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program. If not, see <http://www.gnu.org/licenses/>.

import json
import sys
import os 
import argparse 
from collections import Callable

# local precedence
pyroute2_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(1, pyroute2_root)

from pyroute2 import DiagSocket
from pyroute2.netlink.diag import SS_ESTABLISHED, SS_SYN_SENT, SS_SYN_RECV, SS_FIN_WAIT1, SS_FIN_WAIT2, SS_TIME_WAIT, SS_CLOSE, SS_CLOSE_WAIT, SS_LAST_ACK, SS_LISTEN, SS_CLOSING, SS_ALL, SS_CONN
from socket import AF_UNIX, AF_INET, AF_INET6, IPPROTO_TCP


class Protocol(Callable):

    def __init__(self, fmt='json'):
        raise RuntimeError('not implemented')

    def __call__(self, nl_diag_sk):
        raise RuntimeError('not implemented')


class TCP(Protocol):

    INET_DIAG_MEMINFO    = 1
    INET_DIAG_INFO       = 2
    INET_DIAG_VEGASINFO  = 3
    INET_DIAG_CONG       = 4

    def __init__(self, sk_states=SS_CONN, fmt='json'):
        self._states = sk_states

        fmter = "_fmt_%s" % fmt
        self._fmt = getattr(self, fmter, None)

        if self._fmt == None:
            raise RuntimeError("unknown formatting")

        IDIAG_EXT_FLAGS = [ self.INET_DIAG_MEMINFO, 
                            self.INET_DIAG_INFO, 
                            self.INET_DIAG_VEGASINFO, 
                            self.INET_DIAG_CONG ]

        self.ext_f = 0
        for f in IDIAG_EXT_FLAGS:
            self.ext_f |= (1<<(f-1))

    def __call__(self, nl_diag_sk):
        sstats = nl_diag_sk.get_sock_stats(states=self._states, family=AF_INET, extensions=self.ext_f)
        refined_stats = self._refine_diag_raw(sstats)
        printable = self._fmt(refined_stats)

        print printable
    
    def _refine_diag_raw(self, raw_stats):

        refined = { 'TCP' : { 'flows' : [] } }

        idiag_refine_map = { 
                            'dst' :      'idiag_src',
                            'src' :      'idiag_dst',
                            'src_port' : 'idiag_sport',
                            'dst_port' : 'idiag_dport',
                            'inode' : 'idiag_inode',
                            'iface_idx' :'idiag_if',
                            'retrans' :  'idiag_retrans'
                           }

        for raw_flow in raw_stats:
            vessel = {}
            for k1,k2 in idiag_refine_map.items():
                vessel[k1] = raw_flow[k2]

            for ext_bundle in raw_flow['attrs']:
                vessel = self._refine_extension(vessel, ext_bundle)
            
            refined['TCP']['flows'].append(vessel)

        return refined

    def _refine_extension(self, vessel, raw_ext):
        k, content = raw_ext
        ext_refine_map = {
                          'meminfo' : {
                                     'r' : 'idiag_rmem',
                                     'w' : 'idiag_wmem',
                                     'f' : 'idiag_fmem',
                                     't' : 'idiag_tmem'
                                    }
                         }

        if k == 'INET_DIAG_MEMINFO':
            mem_k = 'meminfo'
            vessel[mem_k] = {}
            for k1, k2 in ext_refine_map[mem_k].items():
                vessel[mem_k][k1] = content[k2]

        elif k == 'INET_DIAG_CONG':
            vessel['cong_algo'] = content

        elif k == 'INET_DIAG_INFO':
            vessel = self._refine_tcp_info(vessel, content)

        elif k == 'INET_DIAG_SHUTDOWN':
            pass

        return vessel

    # interim approach
    # tcpinfo call backs
    class InfoCbCore:

        # normalizer
        @staticmethod
        def rto_n_cb(key, value, **ctx):
            out = None 
            if value != 3000000:
                out = value / 1000.0
                
            return out

        @staticmethod
        def generic_1k_n_cb(key, value, **ctx):
            return value / 1000.0
                
        # predicates
        @staticmethod
        def snd_thresh_p_cb(key, value, **ctx):
            if value < 0xFFFF:
                return value

            return None

        @staticmethod
        def rtt_p_cb(key, value, **ctx):
           tcp_info_raw = ctx['raw']

           try:
               if (tcp_info_raw['tcpv_enabled'] != 0 and
                   tcp_info_raw['tcpv_rtt'] != 0x7fffffff):
                      return tcp_info_raw['tcpv_rtt']
           except KeyError:
               # ill practice, yet except quicker path 
               pass

           return tcp_info_raw['tcpi_rtt'] / 1000.0

        # converter
        @staticmethod
        def state_c_cb(key, value, **ctx):
                state_str_map = {
                                SS_ESTABLISHED : "established",
                                SS_SYN_SENT : "syn-sent",
                                SS_SYN_RECV : "syn-recv",
                                SS_FIN_WAIT1 : "fin-wait-1",
                                SS_FIN_WAIT2 : "fin-wait-2",
                                SS_TIME_WAIT : "time-wait",
                                SS_CLOSE : "unconnected",
                                SS_CLOSE_WAIT : "close-wait",
                                SS_LAST_ACK : "last-ack",
                                SS_LISTEN : 	"listening",
                                SS_CLOSING : "closing"
                                }

                return state_str_map[value]

        @staticmethod
        def opts_c_cb(key, value, **ctx):
            tcp_info_raw = ctx['raw']

            # tcp_info opt flags
            TCPI_OPT_TIMESTAMPS = 1
            TCPI_OPT_SACK = 2
            TCPI_OPT_WSCALE = 4
            TCPI_OPT_ECN = 8

            out = []

            opts = tcp_info_raw['tcpi_options']
            if (opts & TCPI_OPT_TIMESTAMPS):
               out.append("ts")
            if (opts & TCPI_OPT_SACK):
               out.append("sack") 
            if (opts & TCPI_OPT_ECN):
               out.append("ecn")

            return out

    def _refine_tcp_info(self, vessel, tcp_info_raw):

        ti = TCP.InfoCbCore

        info_refine_tabl = {
                            'tcpi_state'                    : ('state'                     , ti.state_c_cb),
                            'tcpi_pmtu'                     : ('pmtu'                      , None),
                            'tcpi_retrans'                  : ('retrans'                   , None),
                            'tcpi_ato'                      : ('ato'                       , ti.generic_1k_n_cb),
                            'tcpi_rto'                      : ('rto'                       , ti.rto_n_cb),
                            # TODO consider wscale baking    
                            'tcpi_snd_wscale'               : ('snd_wscale'                , None),
                            'tcpi_rcv_wscale'               : ('rcv_wscale'                , None),
                            # TODO bps baking               
                            'tcpi_snd_mss'                  : ('snd_mss'                   , None),
                            'tcpi_snd_cwnd'                 : ('snd_cwnd'                  , None),
                            'tcpi_snd_ssthresh'             : ('snd_ssthresh'              , ti.snd_thresh_p_cb),
                            # TODO consider rtt agglomeration - needs nesting
                            'tcpi_rtt'                      : ('rtt'                       , ti.rtt_p_cb),
                            'tcpi_rttvar'                   : ('rttvar'                    , ti.generic_1k_n_cb),
                            'tcpi_rcv_rtt'                  : ('rcv_rtt'                   , ti.generic_1k_n_cb),
                            'tcpi_rcv_space'                : ('rcv_space'                 , None),
                            'tcpi_options'                  : ('opts'                      , ti.opts_c_cb),
                            # unclear, NB not in use by iproute2 ss latest
                            'tcpi_last_data_sent'           : ('last_data_sent'            , None),
                            'tcpi_rcv_ssthresh'             : ('rcv_ssthresh'              , None),
                            'tcpi_rcv_ssthresh'             : ('rcv_ssthresh'              , None),
                            'tcpi_segs_in'                  : ('segs_in'                   , None),
                            'tcpi_segs_out'                 : ('segs_out'                  , None),
                            'tcpi_data_segs_in'             : ('data_segs_in'              , None),
                            'tcpi_data_segs_out'            : ('data_segs_out'             , None),
                            'tcpi_lost'                     : ('lost'                      , None),
                            'tcpi_notsent_bytes'            : ('notsent_bytes'             , None),
                            'tcpi_rcv_mss'                  : ('rcv_mss'                   , None),
                            'tcpi_pacing_rate'              : ('pacing_rate'               , None),
                            'tcpi_retransmits'              : ('retransmits'               , None),
                            'tcpi_min_rtt'                  : ('min_rtt'                   , None),
                            'tcpi_rwnd_limited'             : ('rwnd_limited'              , None),
                            'tcpi_max_pacing_rate'          : ('max_pacing_rate'           , None),
                            'tcpi_probes'                   : ('probes'                    , None),
                            'tcpi_reordering'               : ('reordering'                , None),
                            'tcpi_last_data_recv'           : ('last_data_recv'            , None),
                            'tcpi_bytes_received'           : ('bytes_received'            , None),
                            'tcpi_fackets'                  : ('fackets'                   , None),
                            'tcpi_last_ack_recv'            : ('last_ack_recv'             , None),
                            'tcpi_last_ack_sent'            : ('last_ack_sent'             , None),
                            'tcpi_unacked'                  : ('unacked'                   , None),
                            'tcpi_sacked'                   : ('sacked'                    , None),
                            'tcpi_bytes_acked'              : ('bytes_acked'               , None),
                            'tcpi_delivery_rate_app_limited': ('delivery_rate_app_limited' , None),
                            'tcpi_delivery_rate'            : ('delivery_rate'             , None),
                            'tcpi_sndbuf_limited'           : ('sndbuf_limited'            , None),
                            'tcpi_ca_state'                 : ('ca_state'                  , None),
                            'tcpi_busy_time'                : ('busy_time'                 , None),
                            'tcpi_total_retrans'            : ('total_retrans'             , None),
                            'tcpi_advmss'                   : ('advmss'                    , None),
                            'tcpi_backoff'                  : ( None                       , None),
                            'tcpv_enabled'                  : ( None                       , 'skip'),
                            'tcpv_rttcnt'                   : ( None                       , 'skip'),
                            'tcpv_rtt'                      : ( None                       , 'skip'),
                            'tcpv_minrtt'                   : ( None                       , 'skip'),
                            # BBR
                            'bbr_bw_lo'                     : ( 'bbr_bw_lo'                , None),
                            'bbr_bw_hi'                     : ( 'bbr_bw_hi'                , None),
                            'bbr_min_rtt'                   : ( 'bbr_min_rtt'              , None),
                            'bbr_pacing_gain'               : ( 'bbr_pacing_gain'          , None),
                            'bbr_cwnd_gain'                 : ( 'bbr_cwnd_gain'            , None),
                            # DCTCP
                            'dctcp_enabled'                 : ( 'dctcp_enabled'            , None),
                            'dctcp_ce_state'                : ( 'dctcp_ce_state'           , None),
                            'dctcp_alpha'                   : ( 'dctcp_alpha'              , None),
                            'dctcp_ab_ecn'                  : ( 'dctcp_ab_ecn'             , None),
                            'dctcp_ab_tot'                  : ( 'dctcp_ab_tot'             , None)
                           }
        k_idx = 0
        cb_idx = 1

        info_k = 'tcp_info'
        vessel[info_k] = {}

        # BUG - pyroute2 diag - seems always last info instance from kernel
        if type(tcp_info_raw) != str:
            for k, v in tcp_info_raw.items():
                refined_k = info_refine_tabl[k][k_idx]
                cb = info_refine_tabl[k][cb_idx]
                refined_v = v
                if cb and cb == 'skip':
                    continue
                elif cb:
                    ctx = { 'raw' : tcp_info_raw }
                    refined_v = cb(k, v, **ctx)

                vessel[info_k][refined_k] = refined_v

        return vessel 

    def _fmt_json(self, refined_stats):
        return json.dumps(refined_stats, indent=4)


def prepare_args():
    parser = argparse.ArgumentParser(description=
                                     """
                                     ss2 - socket statistics depictor meant as
                                     a complete and convenient surrogate for iproute2/misc/ss2
                                     """)
    parser.add_argument('-t', '--tcp', help='Display TCP sockets.', action='store_true')
    parser.add_argument('-l', '--listen', help='Display listening sockets.', action='store_true')
    parser.add_argument('-a', '--all', help='Display all sockets.', action='store_true')

    args = parser.parse_args()
    
    return args

def run():
    args = prepare_args()

    protocol = None

    _states = SS_CONN
    if args.listen: 
        _states = (1<<SS_LISTEN)
    if args.all: 
        _states = SS_ALL
    
    if args.tcp:
        protocol = TCP(sk_states=_states)

    if not protocol:
        raise RuntimeError('not implemented - ss2 in fledging mode')

    with DiagSocket() as ds: 
        ds.bind()
        protocol(ds)

if __name__ == "__main__":
    run()
