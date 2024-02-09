from unittest import mock


class TokenManager:
    validate = mock.Mock(name='validate')
    validate.return_value = {'expires_at': '3022.07.04 00:00 CEST'}

    def __init__(self, *argv, **kwarg):
        pass
