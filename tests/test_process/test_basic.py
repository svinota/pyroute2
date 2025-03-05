import errno
import multiprocessing as mp

import pytest

from pyroute2 import NetlinkError, config
from pyroute2.process import ChildProcess

exc_map = {
    'OSError': (OSError, (errno.ENOENT, 'message')),
    'NetlinkError': (NetlinkError, (errno.EEXIST, 'message')),
    'RuntimeError': (RuntimeError, ()),
    'AttributeError': (AttributeError, ()),
    'KeyError': (KeyError, ()),
}


def _child(arg_str, arg_int, arg_bool):
    assert isinstance(arg_str, str)
    assert isinstance(arg_int, int)
    assert isinstance(arg_bool, bool)


def _child_exceptions(exc_type):
    global exc_map
    spec = exc_map[exc_type]
    raise spec[0](*spec[1])


@pytest.mark.parametrize('exc_type', list(exc_map.keys()))
def test_exceptions(exc_type):
    with pytest.raises(exc_map[exc_type][0]) as exc_info:
        with ChildProcess(target=_child_exceptions, args=[exc_type]) as proc:
            proc.communicate()
    print(exc_info)


@pytest.mark.parametrize(
    'mode,check_attr',
    (
        ('fork', lambda x: isinstance(x.pid, int)),
        ('mp', lambda x: isinstance(x.proc, mp.Process)),
    ),
)
def test_modes(mode, check_attr):
    old_mode = config.child_process_mode
    config.child_process_mode = mode
    with ChildProcess(target=_child, args=["str", 1, True]) as proc:
        assert proc.mode == mode
        assert check_attr(proc)
        proc.communicate()
    config.child_process_mode = old_mode


@pytest.mark.parametrize(
    'exc,args', ((AssertionError, ['str', 1, 0]), (TypeError, []))
)
def test_args_fail(exc, args):
    with pytest.raises(exc):
        with ChildProcess(target=_child, args=args) as proc:
            proc.communicate()


def child_process_case_01(x):
    return b' ' * x


def child_process_case_02():
    return None


@pytest.mark.parametrize(
    'func,args,ret',
    (
        (child_process_case_01, [10], (b'          ', [])),
        (child_process_case_02, [], (b'', [])),
    ),
)
def test_simple_args(func, args, ret):
    with ChildProcess(func, args) as proc:
        assert proc.communicate() == ret
