from pyroute2.netlink.generic import ipvs


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
        return self.make_request(cmd, flags)
