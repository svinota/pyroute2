import re
import os
import struct

from pyroute2.common import size_suffixes
from pyroute2.common import time_suffixes
from pyroute2.common import rate_suffixes
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla

LINKLAYER_UNSPEC = 0
LINKLAYER_ETHERNET = 1
LINKLAYER_ATM = 2

ATM_CELL_SIZE = 53
ATM_CELL_PAYLOAD = 48

TC_RED_ECN = 1
TC_RED_HARDDROP = 2
TC_RED_ADAPTATIVE = 4

TIME_UNITS_PER_SEC = 1000000

_psched = open('/proc/net/psched', 'r')
[_t2us,
 _us2t,
 _clock_res,
 _wee] = [int(i, 16) for i in _psched.read().split()]
_clock_factor = float(_clock_res) / TIME_UNITS_PER_SEC
_tick_in_usec = float(_t2us) / _us2t * _clock_factor
_first_letter = re.compile('[^0-9]+')


def _get_hz():
    if _clock_res == 1000000:
        return _wee
    else:
        return os.environ.get('HZ', 1000)


def _get_by_suffix(value, default, func):
    if not isinstance(value, basestring):
        return value
    pos = _first_letter.search(value)
    if pos is None:
        suffix = default
    else:
        pos = pos.start()
        value, suffix = value[:pos], value[pos:]
    value = int(value)
    return func(value, suffix)


def _get_size(size):
    return _get_by_suffix(size, 'b',
                          lambda x, y: x * size_suffixes[y])


def _get_time(lat):
    return _get_by_suffix(lat, 'ms',
                          lambda x, y: (x * TIME_UNITS_PER_SEC) /
                          time_suffixes[y])


def _get_rate(rate):
    return _get_by_suffix(rate, 'bit',
                          lambda x, y: (x * rate_suffixes[y]) / 8)


def _time2tick(t):
    # The current code is ported from tc utility
    return t * _tick_in_usec


def _calc_xmittime(rate, size):
    # The current code is ported from tc utility
    return _time2tick(TIME_UNITS_PER_SEC * (float(size) / rate))


def _red_eval_ewma(qmin, burst, avpkt):
    # The current code is ported from tc utility
    wlog = 1
    W = 0.5
    a = float(burst) + 1 - float(qmin) / avpkt
    assert a < 1

    while wlog < 32:
        wlog += 1
        W /= 2
        if (a <= (1 - pow(1 - W, burst)) / W):
            return wlog
    return -1


def _red_eval_P(qmin, qmax, probability):
    # The current code is ported from tc utility
    i = qmax - qmin
    assert i > 0
    assert i < 32

    probability /= i
    while i < 32:
        i += 1
        if probability > 1:
            break
        probability *= 2
    return i


def get_tbf_parameters(kwarg):
    # rate and burst are required
    rate = _get_rate(kwarg['rate'])
    burst = kwarg['burst']

    # if peak, mtu is required
    peak = _get_rate(kwarg.get('peak', 0))
    mtu = kwarg.get('mtu', 0)
    if peak:
        assert mtu

    # limit OR latency is required
    limit = kwarg.get('limit', None)
    latency = _get_time(kwarg.get('latency', None))
    assert limit or latency

    # calculate limit from latency
    if limit is None:
        rate_limit = rate * float(latency) /\
            TIME_UNITS_PER_SEC + burst
        if peak:
            peak_limit = peak * float(latency) /\
                TIME_UNITS_PER_SEC + mtu
            if rate_limit > peak_limit:
                rate_limit = peak_limit
        limit = rate_limit

    # fill parameters
    return {'attrs': [['TCA_TBF_PARMS', {'rate': rate,
                                         'mtu': mtu,
                                         'buffer': _calc_xmittime(rate, burst),
                                         'limit': limit}],
                      ['TCA_TBF_RTAB', True]]}


def get_sfq_parameters(kwarg):
    kwarg['quantum'] = _get_size(kwarg.get('quantum', 0))
    kwarg['perturb_period'] = kwarg.get('perturb', 0) or \
        kwarg.get('perturb_period', 0)
    limit = kwarg['limit'] = kwarg.get('limit', 0) or \
        kwarg.get('redflowlimit', 0)
    qth_min = kwarg.get('min', 0)
    qth_max = kwarg.get('max', 0)
    avpkt = kwarg.get('avpkt', 1000)
    probability = kwarg.get('probability', 0.02)
    ecn = kwarg.get('ecn', False)
    harddrop = kwarg.get('harddrop', False)
    kwarg['flags'] = kwarg.get('flags', 0)
    if ecn:
        kwarg['flags'] |= TC_RED_ECN
    if harddrop:
        kwarg['flags'] |= TC_RED_HARDDROP
    if kwarg.get('redflowlimit'):
        qth_max = qth_max or limit / 4
        qth_min = qth_min or qth_max / 3
        kwarg['burst'] = kwarg['burst'] or \
            (2 * qth_min + qth_max) / (3 * avpkt)
        assert limit > qth_max
        assert qth_max > qth_min
        kwarg['qth_min'] = qth_min
        kwarg['qth_max'] = qth_max
        kwarg['Wlog'] = _red_eval_ewma(qth_min, kwarg['burst'], avpkt)
        kwarg['Plog'] = _red_eval_P(qth_min, qth_max, probability)
        assert kwarg['Wlog'] >= 0
        assert kwarg['Plog'] >= 0
        kwarg['max_P'] = int(probability * pow(2, 23))

    return kwarg


def get_htb_parameters(kwarg):
    rate2quantum = kwarg.get('r2q', 0xa)
    version = kwarg.get('version', 3)
    defcls = kwarg.get('default', 0x10)
    parent = kwarg.get('parent', None)
    #
    rate = _get_rate(kwarg.get('rate', None))
    ceil = _get_rate(kwarg.get('ceil', 0)) or rate
    #
    prio = kwarg.get('prio', 0)
    mtu = kwarg.get('mtu', 1600)
    mpu = kwarg.get('mpu', 0)
    overhead = kwarg.get('overhead', 0)
    # linklayer = kwarg.get('linklayer', None)
    quantum = kwarg.get('quantum', 0)
    #
    burst = kwarg.get('burst', None) or \
        kwarg.get('maxburst', None) or \
        kwarg.get('buffer', None)
    if rate is not None:
        if burst is None:
            burst = rate / _get_hz() + mtu
        burst = _calc_xmittime(rate, burst)
    cburst = kwarg.get('cburst', None) or \
        kwarg.get('cmaxburst', None) or \
        kwarg.get('cbuffer', None)
    if ceil is not None:
        if cburst is None:
            cburst = ceil / _get_hz() + mtu
        cburst = _calc_xmittime(ceil, cburst)

    if parent is not None:
        # HTB class
        ret = [['TCA_HTB_PARMS', {'buffer': burst,
                                  'cbuffer': cburst,
                                  'quantum': quantum,
                                  'prio': prio,
                                  'rate': rate,
                                  'ceil': ceil,
                                  'ceil_overhead': overhead,
                                  'rate_overhead': overhead,
                                  'rate_mpu': mpu,
                                  'ceil_mpu': mpu}],
               ['TCA_HTB_RTAB', True],
               ['TCA_HTB_CTAB', True]]

    else:
        # HTB root
        ret = [['TCA_HTB_INIT', {'debug': 0,
                                 'defcls': defcls,
                                 'direct_pkts': 0,
                                 'rate2quantum': rate2quantum,
                                 'version': version}]]
    return {'attrs': ret}


class nla_plus_rtab(nla):
    class parms(nla):
        def adjust_size(self, size, mpu, linklayer):
            # The current code is ported from tc utility
            if size < mpu:
                size = mpu

            if linklayer == LINKLAYER_ATM:
                cells = size / ATM_CELL_PAYLOAD
                if size % ATM_CELL_PAYLOAD > 0:
                    cells += 1
                size = cells * ATM_CELL_SIZE

            return size

        def calc_rtab(self, kind):
            # The current code is ported from tc utility
            rtab = []
            mtu = self.get('mtu', 0) or 1600
            cell_log = self['%s_cell_log' % (kind)]
            mpu = self['%s_mpu' % (kind)]
            rate = self['rate']

            # calculate cell_log
            if cell_log == 0:
                while (mtu >> cell_log) > 255:
                    cell_log += 1

            # fill up the table
            for i in range(256):
                size = self.adjust_size((i + 1) << cell_log,
                                        mpu,
                                        LINKLAYER_ETHERNET)
                rtab.append(_calc_xmittime(rate, size))

            self['%s_cell_align' % (kind)] = -1
            self['%s_cell_log' % (kind)] = cell_log
            return rtab

        def encode(self):
            self.rtab = None
            self.ptab = None
            if self.get('rate', False):
                self.rtab = self.calc_rtab('rate')
            if self.get('peak', False):
                self.ptab = self.calc_rtab('peak')
            if self.get('ceil', False):
                self.ctab = self.calc_rtab('ceil')
            nla.encode(self)

    class rtab(nla):
        fields = (('value', 's'), )

        def encode(self):
            parms = self.parent.get_attr('TCA_TBF_PARMS') or \
                self.parent.get_attr('TCA_HTB_PARMS')
            if parms:
                self.value = getattr(parms[0], self.__class__.__name__)
                self['value'] = struct.pack('I' * 256, *self.value)
            nla.encode(self)

        def decode(self):
            nla.decode(self)
            parms = self.parent.get_attr('TCA_TBF_PARMS') or \
                self.parent.get_attr('TCA_HTB_PARMS')
            if parms:
                rtab = struct.unpack('I' * (len(self['value']) / 4),
                                     self['value'])
                self.value = rtab
                setattr(parms[0], self.__class__.__name__, rtab)

    class ptab(rtab):
        pass

    class ctab(rtab):
        pass


class nla_plus_police(nla):
    class police(nla):
        nla_map = (('TCA_POLICE_UNSPEC', 'none'),
                   ('TCA_POLICE_TBF', 'police_tbf'),
                   ('TCA_POLICE_RATE', 'hex'),
                   ('TCA_POLICE_PEAKRATE', 'hex'),
                   ('TCA_POLICE_AVRATE', 'hex'),
                   ('TCA_POLICE_RESULT', 'hex'))

        class police_tbf(nla):
            fields = (('index', 'I'),
                      ('action', 'i'),
                      ('limit', 'I'),
                      ('burst', 'I'),
                      ('mtu', 'I'),
                      ('rate_cell_log', 'B'),
                      ('rate___reserved', 'B'),
                      ('rate_overhead', 'H'),
                      ('rate_cell_align', 'h'),
                      ('rate_mpu', 'H'),
                      ('rate', 'I'),
                      ('peak_cell_log', 'B'),
                      ('peak___reserved', 'B'),
                      ('peak_overhead', 'H'),
                      ('peak_cell_align', 'h'),
                      ('peak_mpu', 'H'),
                      ('peak', 'I'),
                      ('refcnt', 'i'),
                      ('bindcnt', 'i'),
                      ('capab', 'I'))


class tcmsg(nlmsg):
    fields = (('family', 'B'),
              ('pad1', 'B'),
              ('pad2', 'H'),
              ('index', 'i'),
              ('handle', 'I'),
              ('parent', 'I'),
              ('info', 'I'))

    nla_map = (('TCA_UNSPEC', 'none'),
               ('TCA_KIND', 'asciiz'),
               ('TCA_OPTIONS', 'get_options'),
               ('TCA_STATS', 'stats'),
               ('TCA_XSTATS', 'get_xstats'),
               ('TCA_RATE', 'hex'),
               ('TCA_FCNT', 'hex'),
               ('TCA_STATS2', 'stats2'),
               ('TCA_STAB', 'hex'))

    class stats(nla):
        fields = (('bytes', 'Q'),
                  ('packets', 'I'),
                  ('drop', 'I'),
                  ('overlimits', 'I'),
                  ('bps', 'I'),
                  ('pps', 'I'),
                  ('qlen', 'I'),
                  ('backlog', 'I'))

    class stats2(nla):
        nla_map = (('TCA_STATS_UNSPEC', 'none'),
                   ('TCA_STATS_BASIC', 'basic'),
                   ('TCA_STATS_RATE_EST', 'rate_est'),
                   ('TCA_STATS_QUEUE', 'queue'),
                   ('TCA_STATS_APP', 'hex'))

        class basic(nla):
            fields = (('bytes', 'Q'),
                      ('packets', 'Q'))

        class rate_est(nla):
            fields = (('bps', 'I'),
                      ('pps', 'I'))

        class queue(nla):
            fields = (('qlen', 'I'),
                      ('backlog', 'I'),
                      ('drops', 'I'),
                      ('requeues', 'I'),
                      ('overlimits', 'I'))

    def get_xstats(self, *argv, **kwarg):
        kind = self.get_attr('TCA_KIND')
        if kind:
            if kind[0] == 'htb':
                return self.xstats_htb
        return self.hex

    class xstats_htb(nla):
        fields = (('lends', 'I'),
                  ('borrows', 'I'),
                  ('giants', 'I'),
                  ('tokens', 'I'),
                  ('ctokens', 'I'))

    def get_options(self, *argv, **kwarg):
        kind = self.get_attr('TCA_KIND')
        if kind:
            if kind[0] == 'ingress':
                return self.options_ingress
            elif kind[0] == 'pfifo_fast':
                return self.options_pfifo_fast
            elif kind[0] == 'tbf':
                return self.options_tbf
            elif kind[0] == 'sfq':
                if kwarg.get('length', 0) >= \
                        struct.calcsize(self.options_sfq_v1.fmt):
                    return self.options_sfq_v1
                else:
                    return self.options_sfq_v0
            elif kind[0] == 'htb':
                return self.options_htb
            elif kind[0] == 'u32':
                return self.options_u32
            elif kind[0] == 'fw':
                return self.options_fw
        return self.hex

    class options_ingress(nla):
        fields = (('value', 'I'), )

    class options_htb(nla_plus_rtab):
        nla_map = (('TCA_HTB_UNSPEC', 'none'),
                   ('TCA_HTB_PARMS', 'htb_parms'),
                   ('TCA_HTB_INIT', 'htb_glob'),
                   ('TCA_HTB_CTAB', 'ctab'),
                   ('TCA_HTB_RTAB', 'rtab'))

        class htb_glob(nla):
            fields = (('version', 'I'),
                      ('rate2quantum', 'I'),
                      ('defcls', 'I'),
                      ('debug', 'I'),
                      ('direct_pkts', 'I'))

        class htb_parms(nla_plus_rtab.parms):
            fields = (('rate_cell_log', 'B'),
                      ('rate___reserved', 'B'),
                      ('rate_overhead', 'H'),
                      ('rate_cell_align', 'h'),
                      ('rate_mpu', 'H'),
                      ('rate', 'I'),
                      ('ceil_cell_log', 'B'),
                      ('ceil___reserved', 'B'),
                      ('ceil_overhead', 'H'),
                      ('ceil_cell_align', 'h'),
                      ('ceil_mpu', 'H'),
                      ('ceil', 'I'),
                      ('buffer', 'I'),
                      ('cbuffer', 'I'),
                      ('quantum', 'I'),
                      ('level', 'I'),
                      ('prio', 'I'))

    class options_fw(nla_plus_police):
        nla_map = (('TCA_FW_UNSPEC', 'none'),
                   ('TCA_FW_CLASSID', 'uint32'),
                   ('TCA_FW_POLICE', 'police'),
                   ('TCA_FW_INDEV', 'hex'),
                   ('TCA_FW_ACT', 'hex'),
                   ('TCA_FW_MASK', 'hex'))

    class options_u32(nla_plus_police):
        nla_map = (('TCA_U32_UNSPEC', 'none'),
                   ('TCA_U32_CLASSID', 'uint32'),
                   ('TCA_U32_HASH', 'uint32'),
                   ('TCA_U32_LINK', 'hex'),
                   ('TCA_U32_DIVISOR', 'uint32'),
                   ('TCA_U32_SEL', 'u32_sel'),
                   ('TCA_U32_POLICE', 'police'),
                   ('TCA_U32_ACT', 'hex'),
                   ('TCA_U32_INDEV', 'hex'),
                   ('TCA_U32_PCNT', 'u32_pcnt'),
                   ('TCA_U32_MARK', 'u32_mark'))

        class u32_sel(nla):
            fields = (('flags', 'B'),
                      ('offshift', 'B'),
                      ('nkeys', 'B'),
                      ('__align', 'B'),
                      ('offmask', '>H'),
                      ('off', 'H'),
                      ('offoff', 'h'),
                      ('hoff', 'h'),
                      ('hmask', '>I'),
                      ('key_mask', '>I'),
                      ('key_val', '>I'),
                      ('key_off', 'i'),
                      ('key_offmask', 'i'))

        class u32_mark(nla):
            fields = (('val', 'I'),
                      ('mask', 'I'),
                      ('success', 'I'))

        class u32_pcnt(nla):
            fields = (('rcnt', 'Q'),
                      ('rhit', 'Q'),
                      ('kcnts', 'Q'))

    class options_pfifo_fast(nla):
        fields = (('bands', 'i'),
                  ('mark_01', 'B'),
                  ('mark_02', 'B'),
                  ('mark_03', 'B'),
                  ('mark_04', 'B'),
                  ('mark_05', 'B'),
                  ('mark_06', 'B'),
                  ('mark_07', 'B'),
                  ('mark_08', 'B'),
                  ('mark_09', 'B'),
                  ('mark_10', 'B'),
                  ('mark_11', 'B'),
                  ('mark_12', 'B'),
                  ('mark_13', 'B'),
                  ('mark_14', 'B'),
                  ('mark_15', 'B'),
                  ('mark_16', 'B'))

    class options_tbf(nla_plus_rtab):
        nla_map = (('TCA_TBF_UNSPEC', 'none'),
                   ('TCA_TBF_PARMS', 'tbf_parms'),
                   ('TCA_TBF_RTAB', 'rtab'),
                   ('TCA_TBF_PTAB', 'ptab'))

        class tbf_parms(nla_plus_rtab.parms):
            fields = (('rate_cell_log', 'B'),
                      ('rate___reserved', 'B'),
                      ('rate_overhead', 'H'),
                      ('rate_cell_align', 'h'),
                      ('rate_mpu', 'H'),
                      ('rate', 'I'),
                      ('peak_cell_log', 'B'),
                      ('peak___reserved', 'B'),
                      ('peak_overhead', 'H'),
                      ('peak_cell_align', 'h'),
                      ('peak_mpu', 'H'),
                      ('peak', 'I'),
                      ('limit', 'I'),
                      ('buffer', 'I'),
                      ('mtu', 'I'))

    class options_sfq_v0(nla):
        fields = (('quantum', 'I'),
                  ('perturb_period', 'i'),
                  ('limit', 'I'),
                  ('divisor', 'I'),
                  ('flows', 'I'))

    class options_sfq_v1(nla):
        fields = (('quantum', 'I'),
                  ('perturb_period', 'i'),
                  ('limit_v0', 'I'),
                  ('divisor', 'I'),
                  ('flows', 'I'),
                  ('depth', 'I'),
                  ('headdrop', 'I'),
                  ('limit_v1', 'I'),
                  ('qth_min', 'I'),
                  ('qth_max', 'I'),
                  ('Wlog', 'B'),
                  ('Plog', 'B'),
                  ('Scell_log', 'B'),
                  ('flags', 'B'),
                  ('max_P', 'I'),
                  ('prob_drop', 'I'),
                  ('forced_drop', 'I'),
                  ('prob_mark', 'I'),
                  ('forced_mark', 'I'),
                  ('prob_mark_head', 'I'),
                  ('forced_mark_head', 'I'))
