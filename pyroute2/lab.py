import inspect
from unittest import mock

registry = []
use_mock = False


class LAB_API:
    def __init__(self, *argv, **kwarg):
        super().__init__(*argv, **kwarg)
        if use_mock:
            registry.append(self)
            for name, method in inspect.getmembers(
                self, predicate=inspect.ismethod
            ):
                setattr(self, name, mock.MagicMock(name=name, wraps=method))
