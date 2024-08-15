'''
General request and RTNL object data filters.
'''

import weakref
from collections import ChainMap


class RequestProcessor(dict):
    field_filters = tuple()
    mark = tuple()
    context = None
    combined = None

    def __init__(self, context=None, prime=None):
        self.reset_filters()
        self.reset_mark()
        self.context = (
            context if isinstance(context, (dict, weakref.ProxyType)) else {}
        )
        self.combined = ChainMap(self, self.context)
        if isinstance(prime, dict):
            self.update(prime)

    def __setitem__(self, key, value):
        if value is None:
            return
        if key in self:
            del self[key]
        for nkey, nvalue in self.filter(key, value).items():
            super().__setitem__(nkey, nvalue)

    def reset_filters(self):
        self.field_filters = []

    def reset_mark(self):
        self.mark = []

    def items(self):
        for key, value in super().items():
            if key not in self.mark:
                yield key, value

    def get_value(self, key, default=None, mode=None):
        for field_filter in self.field_filters:
            getter = getattr(field_filter, f'get_{key}', None)
            if getter is not None:
                return getter(self, mode)
        self.mark.append(key)
        return self.get(key, default)

    def filter(self, key, value):
        for field_filter in self.field_filters:
            if hasattr(field_filter, 'key_transform'):
                key = field_filter.key_transform(key)
            if (
                hasattr(field_filter, 'allowed')
                and key not in field_filter.allowed
            ):
                return {}
            if hasattr(field_filter, 'policy') and not field_filter.policy(
                key
            ):
                return {}
            setter = getattr(field_filter, f'set_{key}', None)
            if setter is not None:
                return setter(self.combined, value)
        return {key: value}

    def update(self, prime):
        for key, value in tuple(prime.items()):
            self[key] = value

    def add_filter(self, field_filter):
        self.field_filters.append(field_filter)
        return self

    def finalize(self):
        self.update(self)
        for field_filter in self.field_filters:
            if hasattr(field_filter, 'finalize'):
                field_filter.finalize(self.combined)
        return self
