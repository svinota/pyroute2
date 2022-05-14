from .main import FilterDict


class InterfaceFieldFilter(FilterDict):
    def _link(self, key, context, value):
        if isinstance(value, dict):
            return {key: value[key]['index']}
        return {key: value}

    def vxlan_link(self, context, value):
        return self._link('vxlan_link', context, value)

    def link(self, context, value):
        return self._link('link', context, value)

    def master(self, context, value):
        return self._link('master', context, value)

    def address(self, context, value):
        if isinstance(value, str):
            # lower the case
            if not value.islower():
                value = value.lower()
            # convert xxxx.xxxx.xxxx to xx:xx:xx:xx:xx:xx
            if len(value) == 14 and value[4] == value[9] == '.':
                value = ':'.join(
                    [':'.join((x[:2], x[2:])) for x in value.split('.')]
                )
        return {'address': value}
