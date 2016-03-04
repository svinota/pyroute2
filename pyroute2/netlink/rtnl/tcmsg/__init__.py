import types

from pyroute2.netlink import nlmsg
from pyroute2.netlink import nla

import cls_fw
import cls_u32
import sched_bpf
import sched_clsact
import sched_codel
import sched_ingress
import sched_fq_codel
import sched_hfsc
import sched_htb
import sched_netem
import sched_pfifo_fast
import sched_plug
import sched_sfq
import sched_tbf
import sched_template

plugins = {'plug': sched_plug,
           'sfq': sched_sfq,
           'clsact': sched_clsact,
           'codel': sched_codel,
           'fq_codel': sched_fq_codel,
           'hfsc': sched_hfsc,
           'htb': sched_htb,
           'bpf': sched_bpf,
           'tbf': sched_tbf,
           'netem': sched_netem,
           'fw': cls_fw,
           'u32': cls_u32,
           'ingress': sched_ingress,
           'pfifo_fast': sched_pfifo_fast}


class tcmsg(nlmsg):

    prefix = 'TCA_'

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
               ('TCA_STATS2', 'get_stats2'),
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

    def get_plugin(self, plug, *argv, **kwarg):
        # get the plugin name
        kind = self.get_attr('TCA_KIND')
        # get the plugin implementation or the default one
        p = plugins.get(kind, sched_template)
        # get the interface
        interface = getattr(p,
                            plug,
                            getattr(sched_template, plug))
        # if it is a method, run and return the result
        if isinstance(interface, types.FunctionType):
            return interface(self, *argv, **kwarg)
        else:
            return interface

    def get_stats2(self, *argv, **kwarg):
        return self.get_plugin('stats2', *argv, **kwarg)

    def get_xstats(self, *argv, **kwarg):
        return self.get_plugin('stats', *argv, **kwarg)

    def get_options(self, *argv, **kwarg):
        return self.get_plugin('options', *argv, **kwarg)
