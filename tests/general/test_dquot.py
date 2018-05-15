import os
from pyroute2 import DQuotSocket
from utils import require_user


class _TestDQuot(object):

    def setup(self):
        require_user('root')
        # setup the test fs
        os.system('gunzip -c dquot.img.gz >dquot.img')
        with os.popen('losetup -f') as f:
            self.loop = f.read().strip()
        os.system('losetup %s dquot.img' % self.loop)
        os.system('mount %s mnt -o quota' % self.loop)
        os.system('quotacheck mnt')
        os.system('quotaon mnt')

    def test_dquot(self):
        ds = DQuotSocket()

        for i in range(3):
            f = open('mnt/test/%i' % i, 'w')
            f.close()
        for f in os.listdir('mnt/test'):
            os.unlink('mnt/test/%s' % f)

        msgs = ds.get()

        assert len(msgs) == 1
        assert msgs[0].get_attr('QUOTA_NL_A_EXCESS_ID') == os.getuid()

        ds.close()

    def teardown(self):
        os.system('quotaoff mnt')
        os.system('umount mnt')
        os.system('losetup -d %s' % self.loop)
        os.unlink('dquot.img')
