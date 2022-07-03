import getpass

import pytest


def require_root(func=None):
    mark = pytest.mark.skipif(
        getpass.getuser() != 'root', reason='no root access'
    )
    if func:
        return mark(func)
    else:
        return mark
