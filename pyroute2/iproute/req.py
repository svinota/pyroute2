import logging
from collections import OrderedDict

log = logging.getLogger(__name__)


class IPRequest(OrderedDict):
    def __init__(self, obj=None, command=None):
        super(IPRequest, self).__init__()
        self.command = command
        if obj is not None:
            self.update(obj)

    def update(self, obj):
        if obj.get('family', None):
            self['family'] = obj['family']
        for key in obj:
            if key == 'family':
                continue
            v = obj[key]
            if isinstance(v, dict):
                self[key] = dict((x for x in v.items() if x[1] is not None))
            elif v is not None:
                self[key] = v
        self.fix_request()

    def fix_request(self):
        pass

    def set(self, key, value):
        return super(IPRequest, self).__setitem__(key, value)

    def sync_cacheinfo(self):
        pass


class CBRequest(IPRequest):
    '''
    FIXME
    '''

    commands = None
    msg = None

    def __init__(self, *argv, **kwarg):
        self['commands'] = {'attrs': []}

    def __setitem__(self, key, value):
        if value is None:
            return
        if key in self.commands:
            self['commands']['attrs'].append([self.msg.name2nla(key), value])
        else:
            self.set(key, value)
