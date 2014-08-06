
NLT_CONTROL = 0x1
NLT_DGRAM = 0x2
NLT_RESPONSE = 0x4
NLT_NOOP = 0x8
NLT_EXCEPTION = 0x10


class TimeoutError(Exception):
    '''
    IOCore operation timeout
    '''
    pass
