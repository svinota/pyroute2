'''
Eventlet compatibility testing module.

Should not be mixed with other test modules,
since eventlet affects all the runtime.
'''
import uuid
from nose.plugins.skip import SkipTest
from utils import require_user
try:
    import eventlet
except ImportError:
    raise SkipTest('eventlet library is not installed')
from pyroute2.config.asyncio import asyncio_config
from pyroute2 import IPRoute
from pyroute2 import NetNS
from pyroute2 import IPDB

try:
    eventlet.monkey_patch()
except AttributeError:
    raise SkipTest('eventlet library is not installed')
asyncio_config()


class TestBasic(object):

    def test_iproute(self):
        ip = IPRoute()
        try:
            assert len(ip.get_links()) > 1
        except:
            raise
        finally:
            ip.close()

    def test_netns(self):
        require_user('root')
        ns = NetNS(str(uuid.uuid4()))
        try:
            assert len(ns.get_links()) >= 1
        except:
            raise
        finally:
            ns.close()
            ns.remove()

    def test_ipdb(self):
        require_user('root')
        ip = IPDB()
        try:
            assert ip._nl_async is False
            assert len(ip.interfaces.keys()) > 1
        except:
            raise
        finally:
            ip.release()


class _TestComplex(object):

    def test_vrouter(self):
        require_user('root')
        nsid = str(uuid.uuid4())
        ns = NetNS(nsid)
        ipdb = IPDB()
        ipns = IPDB(nl=ns)
        try:
            ipdb.create(ifname='ve0p0', peer='ve0p1', kind='veth').commit()
            ipdb.interfaces.ve0p1.net_ns_fd = nsid
            ipdb.commit()

            with ipns.interfaces.ve0p1 as i:
                i.set_ifname('eth0')
                i.up()

        except:
            raise
        finally:
            ipdb.interfaces.ve0p0.remove()
            ipdb.commit()
            ipdb.release()
            ipns.release()
            ns.remove()
