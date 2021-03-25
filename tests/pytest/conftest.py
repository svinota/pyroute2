import pytest
from pr2test.context_manager import SpecContextManager
from pr2test.context_manager import NDBContextManager


@pytest.fixture
def context(request, tmpdir):
    '''
    This fixture is used to prepare the environment and
    to clean it up after each test.

    https://docs.pytest.org/en/stable/fixture.html
    '''
    #                                       test stage:
    #
    ctx = NDBContextManager(request, tmpdir)  # setup
    yield ctx                                 # execute
    ctx.teardown()                            # cleanup


@pytest.fixture
def spec(request, tmpdir):
    '''
    A simple fixture with only some variables set
    '''
    ctx = SpecContextManager(request, tmpdir)
    yield ctx
    ctx.teardown()
