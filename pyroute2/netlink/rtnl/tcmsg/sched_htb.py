from common import get_hz
from common import get_rate
from common import calc_xmittime
from common import nla_plus_rtab
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl import TC_H_ROOT

parent = TC_H_ROOT


def get_class_parameters(kwarg):
    prio = kwarg.get('prio', 0)
    mtu = kwarg.get('mtu', 1600)
    mpu = kwarg.get('mpu', 0)
    overhead = kwarg.get('overhead', 0)
    quantum = kwarg.get('quantum', 0)
    rate = get_rate(kwarg.get('rate', None))
    ceil = get_rate(kwarg.get('ceil', 0)) or rate

    burst = kwarg.get('burst', None) or \
        kwarg.get('maxburst', None) or \
        kwarg.get('buffer', None)

    if rate is not None:
        if burst is None:
            burst = rate / get_hz() + mtu
        burst = calc_xmittime(rate, burst)

    cburst = kwarg.get('cburst', None) or \
        kwarg.get('cmaxburst', None) or \
        kwarg.get('cbuffer', None)

    if ceil is not None:
        if cburst is None:
            cburst = ceil / get_hz() + mtu
        cburst = calc_xmittime(ceil, cburst)

    return {'attrs': [['TCA_HTB_PARMS', {'buffer': burst,
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
                      ['TCA_HTB_CTAB', True]]}


def get_parameters(kwarg):
    rate2quantum = kwarg.get('r2q', 0xa)
    version = kwarg.get('version', 3)
    defcls = kwarg.get('default', 0x10)

    return {'attrs': [['TCA_HTB_INIT', {'debug': 0,
                                        'defcls': defcls,
                                        'direct_pkts': 0,
                                        'rate2quantum': rate2quantum,
                                        'version': version}]]}


class stats(nla):
    fields = (('lends', 'I'),
              ('borrows', 'I'),
              ('giants', 'I'),
              ('tokens', 'I'),
              ('ctokens', 'I'))


class options(nla_plus_rtab):
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
