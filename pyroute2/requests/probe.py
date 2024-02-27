from .common import NLAKeyTransform


class ProbeFieldFilter(NLAKeyTransform):
    _nla_prefix = 'PROBE_'

    def finalize(self, context):
        if 'kind' not in context:
            context['kind'] = 'ping'
        if 'num' not in context:
            context['num'] = 1
        if 'timeout' not in context:
            context['timeout'] = 1
