from pyroute2.netlink import nla
from pyroute2.netlink.rtnl import TC_H_ROOT
from common import stats2 as c_stats2

parent = TC_H_ROOT


def get_class_parameters(kwarg):
    return {'attrs': [['TCA_DRR_QUANTUM', kwarg.get('quantum', 0)]]}


class options(nla):
    nla_map = (('TCA_DRR_UNSPEC', 'none'),
               ('TCA_DRR_QUANTUM', 'uint32'))


class stats(nla):
    fields = (('deficit', 'I'), )


class stats2(c_stats2):
    class stats_app(stats):
        pass
