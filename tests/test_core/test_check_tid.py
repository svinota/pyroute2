import logging
import threading
import warnings

import pytest

from pyroute2 import IPRoute


def catch_tid_error(ipr):
    try:
        ipr._check_tid(tag='0x8241', level=logging.ERROR)
    except RuntimeError as e:
        assert '#0x8241' in e.args[0]
        warnings.warn('#0x8242')


@pytest.mark.parametrize(
    'func,tag',
    (
        (lambda x: x.bind(), '#bind'),
        (lambda x: x._check_tid(tag='0x8240', level=logging.WARN), '#0x8240'),
        (catch_tid_error, '#0x8242'),
    ),
)
def test_calls(func, tag):
    with warnings.catch_warnings(record=True) as wrec:
        with IPRoute() as ipr:
            t = threading.Thread(target=func, args=[ipr])
            t.start()
            t.join()
        assert len(wrec) == 1
        assert tag in wrec[0].message.args[0]
