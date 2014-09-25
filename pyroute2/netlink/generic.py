import logging
from pyroute2.netlink import nlmsg
from pyroute2.netlink import genlmsg

logging.warning("Usage of pyroute2.netlink.generic "
                "is deprecated, see "
                "http://pyroute2.org/docs/migration.html")
mofules = [nlmsg, genlmsg]
__all__ = ["nlmsg", "genlmsg"]
