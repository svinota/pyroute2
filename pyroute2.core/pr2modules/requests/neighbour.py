import ipaddress

from .main import FilterDict


class NeighbourFieldFilter(FilterDict):
    def index(self, context, value):
        return {'ifindex': value}

    def dst(self, context, value):
        if isinstance(value, str) and ':' in value:
            return {'dst': ipaddress.ip_address(value).compressed}
        return {'dst': value}
