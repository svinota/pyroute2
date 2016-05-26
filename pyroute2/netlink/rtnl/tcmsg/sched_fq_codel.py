import logging
import struct
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl import TC_H_ROOT
from pyroute2.netlink.rtnl.tcmsg import common
from pyroute2.netlink.rtnl.tcmsg.common import get_time

log = logging.getLogger(__name__)
parent = TC_H_ROOT


def get_parameters(kwarg):
    #
    # ACHTUNG: experimental code
    #
    # Parameters naming scheme WILL be changed in next releases
    #
    ret = {'attrs': []}
    transform = {'fqc_limit': lambda x: x,
                 'fqc_flows': lambda x: x,
                 'fqc_quantum': lambda x: x,
                 'fqc_ecn': lambda x: x,
                 'fqc_target': get_time,
                 'fqc_ce_threshold': get_time,
                 'fqc_interval': get_time}
    for key in transform.keys():
        if key in kwarg:
            log.warning('fq_codel parameters naming will be changed '
                        'in next releases (%s)' % key)
            ret['attrs'].append(['TCA_FQ_CODEL_%s' % key[4:].upper(),
                                 transform[key](kwarg[key])])
    return ret


class options(nla):
    nla_map = (('TCA_FQ_CODEL_UNSPEC', 'none'),
               ('TCA_FQ_CODEL_TARGET', 'uint32'),
               ('TCA_FQ_CODEL_LIMIT', 'uint32'),
               ('TCA_FQ_CODEL_INTERVAL', 'uint32'),
               ('TCA_FQ_CODEL_ECN', 'uint32'),
               ('TCA_FQ_CODEL_FLOWS', 'uint32'),
               ('TCA_FQ_CODEL_QUANTUM', 'uint32'),
               ('TCA_FQ_CODEL_CE_THRESHOLD', 'uint32'))


class stats(nla):

    TCA_FQ_CODEL_XSTATS_QDISC = 0
    TCA_FQ_CODEL_XSTATS_CLASS = 1

    qdisc_fields = (('maxpacket', 'I'),
                    ('drop_overlimit', 'I'),
                    ('ecn_mark', 'I'),
                    ('new_flow_count', 'I'),
                    ('new_flows_len', 'I'),
                    ('old_flows_len', 'I'),
                    ('ce_mark', 'I'))

    class_fields = (('deficit', 'i'),
                    ('ldelay', 'I'),
                    ('count', 'I'),
                    ('lastcount', 'I'),
                    ('dropping', 'I'),
                    ('drop_next', 'i'))

    def decode(self):
        nla.decode(self)
        # read the type
        kind = struct.unpack('I', self.buf.read(4))[0]
        if kind == self.TCA_FQ_CODEL_XSTATS_QDISC:
            self.fields = self.qdisc_fields
        elif kind == self.TCA_FQ_CODEL_XSTATS_CLASS:
            self.fields = self.class_fields
        else:
            raise TypeError("Unknown xstats type")
        self.decode_fields()


class stats2(common.stats2):
    class stats_app(stats):
        pass
