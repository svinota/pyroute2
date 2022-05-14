'''
General request and RTNL object data filters.
'''
import weakref
from collections import ChainMap


class RequestProcessor(dict):
    def __init__(self, field_filter, context=None, prime=None):
        self.field_filter = field_filter
        self.context = (
            context if isinstance(context, (dict, weakref.ProxyType)) else {}
        )
        self.combined = ChainMap(self, self.context)
        if isinstance(prime, dict):
            self.update(prime)

    def __setitem__(self, key, value):
        for nkey, nvalue in self.filter(key, value).items():
            super(RequestProcessor, self).__setitem__(nkey, nvalue)

    def filter(self, key, value):
        return getattr(self.field_filter, key, lambda *argv: {key: value})(
            self.combined, value
        )

    def update(self, prime):
        for key, value in prime.items():
            self[key] = value

    def finalize(self, cmd_context):
        if hasattr(self.field_filter, 'finalize'):
            self.field_filter.finalize(self.combined, cmd_context)
        return self
