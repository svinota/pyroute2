import collections
from unittest import mock


class Client(mock.MagicMock):
    def __init__(self, *argv, **kwarg):
        super().__init__(*argv, **kwarg)
        self.SendPacket = mock.Mock(name='SendPacket')
        self.SendPacket.return_value = collections.namedtuple(
            'reply', ['code']
        )(True)
