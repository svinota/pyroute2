import pytest

from pyroute2 import IPRoute


class BasicContextManager:
    def __init__(self, request, tmpdir):
        self.ipr = IPRoute()

    def teardown(self):
        self.ipr.close()


@pytest.fixture
def context(request, tmpdir):
    ctx = BasicContextManager(request, tmpdir)
    yield ctx
    ctx.teardown()
