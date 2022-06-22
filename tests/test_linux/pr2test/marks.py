import getpass

import pytest

def require_root():
    return pytest.mark.skipif(getpass.getuser() != 'root', reason='no root access')
