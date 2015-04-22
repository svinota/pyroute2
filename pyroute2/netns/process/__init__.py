import types
import subprocess


class MetaPopen(type):
    '''
    API definition for NSPopen.

    All this stuff is required to make `help()` function happy.
    '''
    def __init__(cls, *argv, **kwarg):
        super(MetaPopen, cls).__init__(*argv, **kwarg)
        # copy docstrings and create proxy slots
        cls.api = {}
        for attr_name in dir(subprocess.Popen):
            attr = getattr(subprocess.Popen, attr_name)
            cls.api[attr_name] = {}
            cls.api[attr_name]['callable'] = \
                isinstance(attr, (types.MethodType, types.FunctionType))
            cls.api[attr_name]['doc'] = attr.__doc__ \
                if hasattr(attr, '__doc__') else None

    def __dir__(cls):
        return list(cls.api.keys()) + ['release']

    def __getattribute__(cls, key):
        try:
            return type.__getattribute__(cls, key)
        except AttributeError:
            attr = getattr(subprocess.Popen, key)
            if isinstance(attr, (types.MethodType, types.FunctionType)):
                def proxy(*argv, **kwarg):
                    return attr(*argv, **kwarg)
                proxy.__doc__ = attr.__doc__
                proxy.__objclass__ = cls
                return proxy
            else:
                return attr
