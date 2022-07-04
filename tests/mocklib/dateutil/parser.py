from unittest import mock


class parse(mock.Mock):
    def __init__(self, *argv, **kwarg):
        super().__init__(*argv, **kwarg)
        self.timestamp = mock.Mock(name='timestamp')
        self.timestamp.return_value = 3313938316
