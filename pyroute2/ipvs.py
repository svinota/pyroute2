'''
IPVS -- IP Virtual Server
-------------------------

IPVS configuration is done via generic netlink protocol.
At the low level one can use it with a GenericNetlinkSocket,
binding it to "IPVS" generic netlink family.

But for the convenience the library provides utility classes:

    * IPVS -- a socket class to access the API
    * IPVSService -- a class to define IPVS service records
    * IPVSDest -- a class to define real server records

An example to dump all the records::

    from pyroute2 import IPVS, IPVSDest, IPVSService

    # run the socket
    ipvs = IPVS()

    # iterate all the IPVS services
    for s in ipvs.service("dump"):

        # create a utility object from a netlink message
        service = IPVSService.from_message(s)
        print("Service: ", service)

        # iterate all the real servers for this service
        for d in ipvs.dest("dump", service=service):

            # create and print a utility object
            dest = IPVSDest.from_message(d)
            print("  Real server: ", dest)

'''

from pyroute2.netlink.generic import ipvs
from pyroute2.requests.common import NLAKeyTransform
from pyroute2.requests.main import RequestProcessor


class ServiceFieldFilter(NLAKeyTransform):
    _nla_prefix = 'IPVS_SVC_ATTR_'


class DestFieldFilter(NLAKeyTransform):
    _nla_prefix = 'IPVS_DEST_ATTR_'


class NLAFilter(RequestProcessor):
    msg = None
    keys = tuple()
    field_filter = None
    nla = None

    def __init__(self, prime):
        super().__init__(prime=prime)

    @classmethod
    def from_message(cls, msg):
        obj = cls({})
        for key, value in msg.get(cls.nla)["attrs"]:
            obj[key] = value
        obj.pop("stats", None)
        obj.pop("stats64", None)
        return obj

    def dump_nla(self, items=None):
        if items is None:
            items = self.items()
        self.update(self)
        self.finalize()
        return {
            "attrs": list(
                map(lambda x: (self.msg.name2nla(x[0]), x[1]), items)
            )
        }

    def dump_key(self):
        return self.dump_nla(
            items=filter(lambda x: x[0] in self.keys, self.items())
        )


class IPVSService(NLAFilter):
    field_filter = ServiceFieldFilter()
    msg = ipvs.ipvsmsg.service
    keys = ("af", "protocol", "addr", "port")
    nla = "IPVS_CMD_ATTR_SERVICE"


class IPVSDest(NLAFilter):
    field_filter = DestFieldFilter()
    msg = ipvs.ipvsmsg.dest
    nla = "IPVS_CMD_ATTR_DEST"


class IPVS(ipvs.IPVSSocket):

    def service(self, command, **kwarg):
        command_map = {
            "add": (ipvs.IPVS_CMD_NEW_SERVICE, "create"),
            "set": (ipvs.IPVS_CMD_SET_SERVICE, "change"),
            "update": (ipvs.IPVS_CMD_DEL_SERVICE, "change"),
            "del": (ipvs.IPVS_CMD_DEL_SERVICE, "req"),
            "get": (ipvs.IPVS_CMD_GET_SERVICE, "get"),
            "dump": (ipvs.IPVS_CMD_GET_SERVICE, "dump"),
        }
        cmd, flags = self.make_request_type(command, command_map)
        msg = ipvs.ipvsmsg()
        msg["cmd"] = cmd
        msg["version"] = ipvs.GENL_VERSION
        return self.nlm_request(msg, msg_type=self.prid, msg_flags=flags)

    def dest(self, command, service, dest=None, **kwarg):
        command_map = {
            "add": (ipvs.IPVS_CMD_NEW_DEST, "create"),
            "set": (ipvs.IPVS_CMD_SET_DEST, "change"),
            "update": (ipvs.IPVS_CMD_DEL_DEST, "change"),
            "del": (ipvs.IPVS_CMD_DEL_DEST, "req"),
            "get": (ipvs.IPVS_CMD_GET_DEST, "get"),
            "dump": (ipvs.IPVS_CMD_GET_DEST, "dump"),
        }
        cmd, flags = self.make_request_type(command, command_map)
        msg = ipvs.ipvsmsg()
        msg["cmd"] = cmd
        msg["version"] = 0x1
        msg["attrs"] = [("IPVS_CMD_ATTR_SERVICE", service.dump_key())]
        if dest is not None:
            msg["attrs"].append("IPVS_CMD_ATTR_SERVICE", dest.dump_nla())
        return self.nlm_request(msg, msg_type=self.prid, msg_flags=flags)
