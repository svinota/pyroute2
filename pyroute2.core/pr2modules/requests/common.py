import ipaddress
from socket import AF_INET6


class IPTargets:
    def _target(self, key, context, value):
        ret = {key: value}
        if isinstance(value, str):
            if value.find('/') >= 0:
                value, prefixlen = value.split('/')
                ret[key] = value
                ret[f'{key}_len'] = int(prefixlen)
            if ':' in value:
                ret[key] = value = ipaddress.ip_address(value).compressed
                ret['family'] = AF_INET6
            if value in ('0', '0.0.0.0', '::', '::/0'):
                ret[key] = ''
        return ret

    def dst(self, context, value):
        if value == 'default':
            return {'dst': ''}
        elif value in ('::', '::/0'):
            return {'dst': '', 'family': AF_INET6}
        return self._target('dst', context, value)

    def src(self, context, value):
        return self._target('src', context, value)

    def gateway(self, context, value):
        if isinstance(value, str) and ':' in value:
            return {'gateway': ipaddress.ip_address(value).compressed}
        return {'gateway': value}


class Index:
    def index(self, context, value):
        if isinstance(value, (list, tuple)):
            value = value[0]
        return {'index': value}
