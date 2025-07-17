import errno

import pytest
from pr2test.context_manager import skip_if_not_supported

from pyroute2 import DL


@pytest.fixture
def netdevsim():
    # Create a netdevsim device and cleanup upon exit, otherwise
    # even an unused netdevsim affects RTNL tests
    #
    own_device = False
    try:
        # Trying to create an existing netdevsim device will
        # result in errno.ENOSPC, then just ignore it: we only
        # need a device to list
        with open('/sys/bus/netdevsim/new_device', 'w') as f:
            f.write('1 0')
        own_device = True
    except OSError as e:
        if e.errno != errno.ENOSPC:
            raise
    try:
        yield
    finally:
        if own_device:
            with open('/sys/bus/netdevsim/del_device', 'w') as f:
                f.write('1 0')


@skip_if_not_supported
def test_list(netdevsim):
    with DL() as dl:
        dls = dl.get_dump()
        if not dls:
            raise RuntimeError('no devlink devices found')

        assert dl.list()
