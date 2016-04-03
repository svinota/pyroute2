# How long should we wait on EACH commit() checkpoint: for ipaddr,
# ports etc. That's not total commit() timeout.
SYNC_TIMEOUT = 5


class DeprecationException(Exception):
    pass


class CommitException(Exception):
    pass


class CreateException(Exception):
    pass


class PartialCommitException(Exception):
    pass
