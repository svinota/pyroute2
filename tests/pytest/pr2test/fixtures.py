import pytest
from pr2test.ctx_managers import NDBContextManager


@pytest.fixture
def local_ctx(tmpdir):
    '''
    This fixture is used to prepare the environment and
    to clean it up after each test.

    https://docs.pytest.org/en/stable/fixture.html
    '''
    #                              test stage:
    #
    ctx = NDBContextManager(tmpdir)  # setup
    yield ctx                        # execute
    ctx.teardown()                   # cleanup
