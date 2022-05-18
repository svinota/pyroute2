import errno
from uuid import uuid4

import pytest
from pr2test.context_manager import NDBContextManager, SpecContextManager
from utils import require_user

from pyroute2.ipset import IPSet, IPSetError
from pyroute2.wiset import COUNT


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


@pytest.fixture(params=(None, IPSet))
def wiset_sock(request):
    if request.param is None:
        yield None
    else:
        before_count = COUNT["count"]
        with IPSet() as sock:
            yield sock
        assert before_count == COUNT['count']
