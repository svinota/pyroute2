import os
import subprocess
import sys

import pytest
from pr2test.marks import require_root

from pyroute2 import DQuotSocket

pytestmark = [
    pytest.mark.skipif(
        sys.version_info < (3, 7),
        reason='the test module requires Python > 3.6',
    ),
    require_root(),
]


class DQuotContextManager:
    def __init__(self):
        self.root = 'test_linux/test_dquot'
        self.gz_image = f'{self.root}/dquot.img.gz'
        self.image = f'{self.root}/dquot.img'
        self.loop = None
        self.mnt = f'{self.root}/mnt'
        self.ds = DQuotSocket()

    def setup(self):
        self.run(f'gunzip -c {self.gz_image} >{self.image}', shell=True)
        self.loop = self.run(['losetup', '-f']).stdout.strip().decode('utf-8')
        st_rdev = os.stat(self.loop).st_rdev
        self.major = os.major(st_rdev)
        self.minor = os.minor(st_rdev)
        self.run(['losetup', self.loop, self.image])
        self.run(['mkdir', '-p', self.mnt])
        self.run(['mount', self.loop, self.mnt, '-o', 'quota'])
        self.run(['quotacheck', self.mnt])
        self.run(['quotaon', self.mnt])

    def run(self, cmd, shell=False, check=True, capture_output=True):
        return subprocess.run(
            cmd, shell=shell, check=check, capture_output=capture_output
        )

    def teardown(self):
        self.ds.close()
        self.run(['quotaoff', self.mnt], check=False)
        self.run(['umount', self.mnt], check=False)
        self.run(['losetup', '-d', self.loop], check=False)
        os.unlink(self.image)

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.teardown()

    def get_one_msg(self):
        for msg in self.ds.get():
            return msg

    def remove_file(self, fname):
        os.unlink(f'{self.mnt}/{fname}')


@pytest.fixture
def mnt():
    with DQuotContextManager() as cm:
        yield cm


def test_basic(mnt):
    mnt.remove_file('test/0')
    msg = mnt.get_one_msg()
    assert msg.get_attr('QUOTA_NL_A_EXCESS_ID') == os.getuid()
    assert msg.get_attr('QUOTA_NL_A_DEV_MAJOR') == mnt.major
    assert msg.get_attr('QUOTA_NL_A_DEV_MINOR') == mnt.minor
