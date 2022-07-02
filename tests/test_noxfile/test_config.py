import ast
import collections
import inspect

import nox
import pytest

# load nox sessions into the registry
import noxfile  # noqa: F401

# load all defined sessions using nox discovery
nox_sessions = nox.registry.get().values()


@pytest.fixture
def session(request):
    # get closure vars, if any
    cvars = inspect.getclosurevars(request.param.func).nonlocals
    yield collections.namedtuple('Session', ('src_func', 'has_user_config'))(
        cvars['func'] if cvars and 'func' in cvars else request.param.func,
        hasattr(request.param.func, '__has_user_config__'),
    )


@pytest.mark.parametrize('session', nox_sessions, indirect=True)
def test_options_call(session):
    # walk the AST tree
    for node in ast.walk(ast.parse(inspect.getsource(session.src_func))):
        # filter only plain function calls, no attributes
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # lookup call `options(...)`
            if node.func.id == 'options':
                # only for decorated by `add_session_config`
                assert session.has_user_config
                # check the arguments
                assert len(node.args) == 2
                assert isinstance(node.args[0], ast.Constant)
                assert isinstance(node.args[1], ast.Name)
                assert node.args[1].id == 'config'


@pytest.mark.parametrize('session', nox_sessions, indirect=True)
def test_session_parameters(session):
    args = inspect.getfullargspec(session.src_func).args
    if session.has_user_config:
        assert args == ['session', 'config']
    else:
        assert args == ['session']
