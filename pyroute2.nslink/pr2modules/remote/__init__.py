try:
    from .iproute import RemoteIPRoute
except ImportError:
    from pr2modules.common import failed_class

    RemoteIPRoute = failed_class('mitogen library is not installed')

classes = [RemoteIPRoute]
