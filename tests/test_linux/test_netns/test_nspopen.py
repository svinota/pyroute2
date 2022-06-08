import fcntl
import os
import subprocess

import pytest

from pyroute2 import NSPopen


def test_basic(context):
    nsid = context.new_nsname
    # create NS and run a child
    nsp = NSPopen(
        nsid, ['ip', '-o', 'link'], stdout=subprocess.PIPE, flags=os.O_CREAT
    )
    ret = nsp.communicate()[0].decode('utf-8')
    host_links = [x.ifname for x in context.ndb.interfaces]
    netns_links = [
        x.split(':')[1].split('@')[0].strip()
        for x in ret.split('\n')
        if len(x)
    ]
    assert nsp.wait() == nsp.returncode == 0
    assert set(host_links) & set(netns_links) == set(netns_links)
    assert set(netns_links) < set(host_links)
    assert not set(netns_links) > set(host_links)
    nsp.release()


def test_release(context):
    nsid = context.new_nsname
    nsp = NSPopen(nsid, ['true'], flags=os.O_CREAT, stdout=subprocess.PIPE)
    nsp.communicate()
    nsp.wait()
    nsp.release()
    with pytest.raises(RuntimeError):
        assert nsp.returncode


def test_stdio(context):
    nsid = context.new_nsname
    nsp = NSPopen(nsid, ['ip', 'ad'], flags=os.O_CREAT, stdout=subprocess.PIPE)
    output = nsp.stdout.read()
    nsp.release()
    assert output is not None


def test_fcntl(context):
    nsid = context.new_nsname
    nsp = NSPopen(nsid, ['ip', 'ad'], flags=os.O_CREAT, stdout=subprocess.PIPE)
    flags = nsp.stdout.fcntl(fcntl.F_GETFL)
    nsp.release()
    assert flags == 0


def test_api_class(context):
    api_nspopen = set(dir(NSPopen))
    api_popen = set(dir(subprocess.Popen))
    assert api_nspopen & api_popen == api_popen


def test_api_object(context):
    nsid = context.new_nsname
    nsp = NSPopen(nsid, ['true'], flags=os.O_CREAT, stdout=subprocess.PIPE)
    smp = subprocess.Popen(['true'], stdout=subprocess.PIPE)
    nsp.communicate()
    smp.communicate()
    api_nspopen = set(dir(nsp))
    api_popen = set(dir(smp))
    minimal = set(('communicate', 'kill', 'wait'))
    assert minimal & (api_nspopen & api_popen) == minimal
    smp.wait()
    nsp.wait()
    assert nsp.returncode == smp.returncode == 0
    nsp.release()
