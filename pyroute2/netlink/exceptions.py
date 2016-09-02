import os


class NetlinkError(Exception):
    '''
    Base netlink error
    '''
    def __init__(self, code, msg=None):
        msg = msg or os.strerror(code)
        super(NetlinkError, self).__init__(code, msg)
        self.code = code


class NetlinkDecodeError(Exception):
    '''
    Base decoding error class.

    Incapsulates underlying error for the following analysis
    '''
    def __init__(self, exception):
        self.exception = exception


class NetlinkHeaderDecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding a header
    '''
    pass


class NetlinkDataDecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding the message fields
    '''
    pass


class NetlinkNLADecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding NLA chain
    '''
    pass


class IPSetError(NetlinkError):
    '''
    Netlink error with IPSet special error codes.

    Messages are imported from errcode.c
    '''
    def __init__(self, code, msg=None):
        if code in self.error_map:
            msg = self.error_map[code]
        super(IPSetError, self).__init__(code, msg)

    error_map = {4097: "Kernel error received: ipset protocol error",
                 4098: "Kernel error received: set type not supported",
                 4099: "Kernel error received: maximal number of sets reached,"
                       " cannot create more.",
                 4100: "Set cannot be destroyed: it is in use by a kernel"
                       " component",
                 4101: "Set cannot be renamed: a set with the new name already"
                       " exists / Sets cannot be swapped: the second set does"
                       " not exist",
                 4102: "The sets cannot be swapped: their type does not match",
                 4103: "Element cannot be added to the set: it's already"
                       " added",
                 4104: "The value of the CIDR parameter of the IP address is"
                       " invalid",
                 4105: "The value of the netmask parameter is invalid",
                 4106: "Protocol family not supported by the set type",
                 4107: "Timeout cannot be used: set was created without"
                       " timeout support",
                 4108: "Set cannot be renamed: it is in use by another system",
                 4109: "An IPv4 address is expected, but not received",
                 4110: "An IPv6 address is expected, but not received",
                 4111: "Packet/byte counters cannot be used: set was created"
                       " without counter support",
                 4112: "Comment string is too long!",
                 4113: "The value of the markmask parameter is invalid",
                 4114: "Skbinfo mapping cannot be used: set was created "
                       " without skbinfo support"}
