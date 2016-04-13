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
