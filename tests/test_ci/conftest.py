import pytest

from pyroute2 import config, netns

config.mock_netlink = True
config.mock_netns = True
pytest_plugins = ["pyroute2.fixtures.iproute", "pyroute2.fixtures.plan9"]
cleanup_netns_set = set()


@pytest.fixture
def netns_create_list():
    return set([x[0][0] for x in netns.create().call_args_list if x[0]])


@pytest.fixture
def netns_remove_list():
    return set([x[0][0] for x in netns.remove().call_args_list if x[0]])


def check_fixture_spec_func(fixture, scope, name):
    spec = fixture._pytestfixturefunction
    return all((spec.name == name, spec.scope == scope))


@pytest.fixture
def check_fixture_spec():
    yield check_fixture_spec_func


@pytest.fixture
def cleanup_netns():
    global cleanup_netns_set
    yield cleanup_netns_set
