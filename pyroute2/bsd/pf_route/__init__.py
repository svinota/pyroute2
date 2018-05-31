from pyroute2 import config

if config.uname[0] == 'FreeBSD':
    from pyroute2.bsd.pf_route.freebsd import (bsdmsg,
                                               if_msg,
                                               rt_msg,
                                               ifa_msg,
                                               ifma_msg,
                                               if_announcemsg)
elif config.uname[0] == 'OpenBSD':
    from pyroute2.bsd.pf_route.openbsd import (bsdmsg,
                                               if_msg,
                                               rt_msg,
                                               ifa_msg,
                                               ifma_msg,
                                               if_announcemsg)
else:
    raise ImportError('platform not supported')

__all__ = (bsdmsg,
           if_msg,
           rt_msg,
           ifa_msg,
           ifma_msg,
           if_announcemsg)
