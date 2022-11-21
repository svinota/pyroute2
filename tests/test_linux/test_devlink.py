from pr2test.context_manager import skip_if_not_supported

from pyroute2 import DL


@skip_if_not_supported
def test_list():
    with DL() as dl:
        dls = dl.get_dump()
        if not dls:
            raise RuntimeError('no devlink devices found')

        assert dl.list()
