'''
General request and RTNL object data filters.
'''
import weakref


class FilterDict:
    def __getitem__(self, key):
        return getattr(self, key)

    def __contains__(self, key):
        return key in vars(type(self))


class RequestProcessor(dict):
    def __init__(self, field_filter, context=None, prime=None):
        self.field_filter = field_filter
        self.context = (
            context if isinstance(context, (dict, weakref.ProxyType)) else {}
        )
        if isinstance(prime, dict):
            self.update(prime)

    def __setitem__(self, key, value):
        for nkey, nvalue in self.filter(key, value).items():
            super(RequestProcessor, self).__setitem__(nkey, nvalue)

    def filter(self, key, value):
        if key in self.field_filter:
            return self.field_filter[key](self.context, value)
        return {key: value}

    def update(self, prime):
        for key, value in prime.items():
            self[key] = value
