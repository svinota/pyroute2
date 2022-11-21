from unittest import mock


class TokenManager(mock.Mock):
    def __init__(self, *argv, **kwarg):
        super().__init__(*argv, **kwarg)
        self.validate = mock.Mock(name='validate')
        self.validate.return_value = {'expires_at': '3022.07.04 00:00 CEST'}
