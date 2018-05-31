# -*- coding: utf-8 -*-
from pyroute2 import config
from pyroute2.iproute.linux import IPRouteMixin
from pyroute2.iproute.linux import IPBatch


if config.uname[0] == 'Linux':
    from pyroute2.iproute.linux import IPRoute
    from pyroute2.iproute.linux import RawIPRoute
elif config.uname[0][-3:] == 'BSD':
    from pyroute2.iproute.bsd import IPRoute
    from pyroute2.iproute.bsd import RawIPRoute
else:
    raise ImportError('no IPRoute module for the platform')

classes = [IPRouteMixin,
           IPBatch,
           IPRoute,
           RawIPRoute]
