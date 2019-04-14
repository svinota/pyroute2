

class SyncStart(Exception):
    pass


class SchemaFlush(Exception):
    pass


class MarkFailed(Exception):
    pass


class DBMExitException(Exception):
    pass


class ShutdownException(Exception):
    pass


class InvalidateHandlerException(Exception):
    pass
