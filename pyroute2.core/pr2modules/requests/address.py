import ipaddress

from pr2modules.common import dqn2int

from .common import Index


class AddressFieldFilter(Index):
    def prefixlen(self, context, value):
        if isinstance(value, str):
            if '.' in value:
                value = dqn2int(value)
            value = int(value)
        return {'prefixlen': value}

    def address(self, context, value):
        ret = {'address': value}
        if isinstance(value, str):
            addr_spec = value.split('/')
            ret['address'] = addr_spec[0]
            if len(addr_spec) > 1:
                ret.update(self.prefixlen('prefixlen', addr_spec[1]))
            if ':' in ret['address']:
                ret['address'] = ipaddress.ip_address(
                    ret['address']
                ).compressed
        return ret
