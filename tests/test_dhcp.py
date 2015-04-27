import gc
import os
import subprocess
import dhclient
from utils import require_user
from utils import require_executable
from pyroute2 import IPDB
from pyroute2.dhcp import BOOTREPLY
from pyroute2.dhcp import DHCPACK


class TestDhcpClient(object):

    def setup(self):
        require_user('root')
        require_executable('busybox')
        self.ip = IPDB()
        # create internal network
        self.if1 = 'dh1-%i' % os.getpid()
        self.if2 = 'dh2-%i' % os.getpid()
        self.ip.create(kind='veth', ifname=self.if1, peer=self.if2).commit()
        # set interfaces up
        with self.ip.interfaces[self.if1] as i:
            i.add_ip('172.16.101.1/24')
            i.up()

        with self.ip.interfaces[self.if2] as i:
            i.up()
        # prepare configuration for udhcpd
        with open('udhcpd.conf.in', 'r') as conf_in:
            with open('udhcpd.conf', 'w') as conf_out:
                conf_out.write('interface %s\n' % self.if1)
                conf_out.write(conf_in.read())
        # run busybox dhcp server on $if1
        with open(os.devnull, 'w') as fnull:
            subprocess.check_call(['busybox', 'udhcpd', 'udhcpd.conf'],
                                  stdout=fnull,
                                  stderr=fnull)

    def teardown(self):
        # read pid from file and kill the server
        with open('udhcpd.pid', 'r') as pid_file:
            pid = int(pid_file.read())
            os.kill(pid, 15)
        # teardown interfaces (enough to remove only master)
        self.ip.interfaces[self.if1].remove().commit()
        # release IPDB
        self.ip.release()
        # remove configuration file
        os.unlink('udhcpd.conf')
        # collect garbage
        gc.collect()

    def test_defaults(self):
        msg = dhclient.action(self.if2)
        assert msg['yiaddr'].startswith('172.16.101.')
        assert msg['op'] == BOOTREPLY
        assert msg['options']['message_type'] == DHCPACK
        assert msg['options']['router'] == ['172.16.101.1']
        assert msg['options']['server_id'] == '172.16.101.1'
        assert msg['options']['subnet_mask'] == '255.255.255.0'
        assert set(msg['options']['name_server']) ==\
            set(('172.16.101.1', '172.16.101.2'))
