import ipaddress
from socket import AF_INET, AF_INET6

from pr2modules.common import dqn2int, get_address_family, getbroadcast

from .common import Index, NLAKeyTransform


class AddressFieldFilter(Index, NLAKeyTransform):

    _nla_prefix = 'IFA_'

    def set_prefixlen(self, context, value):
        if isinstance(value, str):
            if '.' in value:
                value = dqn2int(value)
            value = int(value)
        return {'prefixlen': value}

    def set_address(self, context, value):
        ret = {'address': value}
        if isinstance(value, str):
            addr_spec = value.split('/')
            ret['address'] = addr_spec[0]
            if len(addr_spec) > 1:
                ret.update(self.set_prefixlen(context, addr_spec[1]))
            if ':' in ret['address']:
                ret['address'] = ipaddress.ip_address(
                    ret['address']
                ).compressed
        return ret

    def set_mask(self, context, value):
        return {'prefixlen': value}

    def _cacheinfo(self, key, value):
        return {key: value, 'cacheinfo': {}}

    def set_preferred_lft(self, context, value):
        return self._cacheinfo('preferred', value)

    def set_preferred(self, context, value):
        return self._cacheinfo('preferred', value)

    def set_valid_lft(self, context, value):
        return self._cacheinfo('valid', value)

    def set_valid(self, context, value):
        return self._cacheinfo('valid', value)

    def finalize_for_iproute(self, context, cmd_context):
        if cmd_context != 'dump':
            if 'cacheinfo' in context:
                cacheinfo = context['cacheinfo']
                for i in ('preferred', 'valid'):
                    cacheinfo[f'ifa_{i}'] = context.get(i, pow(2, 32) - 1)
            if 'family' not in context:
                context['family'] = get_address_family(context['address'])
            if 'prefixlen' not in context:
                if context['family'] == AF_INET:
                    context['prefixlen'] = 32
                elif context['family'] == AF_INET6:
                    context['prefixlen'] = 128
            if 'local' not in context and context['family'] == AF_INET:
                # inject IFA_LOCAL, if family is AF_INET and
                # IFA_LOCAL is not set
                context['local'] = context['address']
            if context.get('broadcast') is True:
                context['broadcast'] = getbroadcast(
                    context['address'], context['prefixlen'], context['family']
                )
