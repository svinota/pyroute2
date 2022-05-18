import pyroute2


def test_exceptions():
    assert issubclass(pyroute2.NetlinkError, Exception)
    assert issubclass(pyroute2.CreateException, Exception)
    assert issubclass(pyroute2.CommitException, Exception)
