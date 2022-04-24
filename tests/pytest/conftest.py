import errno
import pytest
from pr2test.context_manager import SpecContextManager
from pr2test.context_manager import NDBContextManager
from pyroute2.ipset import IPSet, IPSetError
from utils import require_user
from uuid import uuid4


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
    yield ctx  # execute
    ctx.teardown()  # cleanup


@pytest.fixture
def spec(request, tmpdir):
    '''
    A simple fixture with only some variables set
    '''
    ctx = SpecContextManager(request, tmpdir)
    yield ctx
    ctx.teardown()


@pytest.fixture
def ipset():
    require_user('root')
    sock = IPSet()
    yield sock
    sock.close()


@pytest.fixture
def ipset_name(ipset):
    name = str(uuid4())[:16]
    yield name
    try:
        ipset.destroy(name)
    except IPSetError as e:
        if e.code != errno.ENOENT:
            raise
