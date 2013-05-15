
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla


class tcmsg(nlmsg):
    t_fields = (('family', 'B'),
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
               ('TCA_XSTATS', 'hex'),
               ('TCA_RATE', 'hex'),
               ('TCA_FCNT', 'hex'),
               ('TCA_STATS2', 'stats2'),
               ('TCA_STAB', 'hex'))

    class stats(nla):
        t_fields = (('bytes', 'Q'),
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
            t_fields = (('bytes', 'Q'),
                        ('packets', 'Q'))

        class rate_est(nla):
            t_fields = (('bps', 'I'),
                        ('pps', 'I'))

        class queue(nla):
            t_fields = (('qlen', 'I'),
                        ('backlog', 'I'),
                        ('drops', 'I'),
                        ('requeues', 'I'),
                        ('overlimits', 'I'))

    def get_options(self):
        kind = self.get_attr('TCA_KIND')
        if kind:
            if kind[0] == 'pfifo_fast':
                return self.options_pfifo_fast
            elif kind[0] == 'tbf':
                return self.options_tbf
        return self.hex

    class options_pfifo_fast(nla):
        fmt = 'i' + 'B' * 16
        fields = tuple(['bands'] + ['mark_%02i' % (i) for i in range(1, 17)])

    class options_tbf(nla):
        nla_map = (('TCA_TBF_UNSPEC', 'none'),
                   ('TCA_TBF_PARMS', 'parms'),
                   ('TCA_TBF_RTAB', 'hex'),
                   ('TCA_TBF_PTAB', 'hex'))

        class parms(nla):
            t_fields = (('rate_cell_log', 'B'),
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
