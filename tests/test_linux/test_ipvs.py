from socket import IPPROTO_TCP

import pytest

from pyroute2 import IPVS, IPVSService


class Context:
    def __init__(self, request, tmpdir):
        self.ipvs = IPVS()
        self.services = []

    def new_service(self, addr, port, protocol):
        service = IPVSService(addr=addr, port=port, protocol=protocol)
        self.ipvs.service("add", service=service)
        self.services.append(service)
        return service

    def teardown(self):
        for service in self.services:
            self.ipvs.service("del", service=service)
        self.services = []

    def service(self, command, service=None):
        return self.ipvs.service(command, service)

    def dest(self, command, service, dest=None):
        return self.ipvs.dest(command, service, dest)


@pytest.fixture
def ipvsadm(request, tmpdir):
    ctx = Context(request, tmpdir)
    yield ctx
    ctx.teardown()


def test_basic(ipvsadm, context):
    ipaddr = context.new_ipaddr
    (
        context.ndb.interfaces[context.default_interface.ifname]
        .add_ip(f"{ipaddr}/24")
        .commit()
    )
    ipvsadm.new_service(addr=ipaddr, port=6000, protocol=IPPROTO_TCP)
    buffer = []
    for service in ipvsadm.service("dump"):
        if (
            service.get(('service', 'addr')) == ipaddr
            and service.get(('service', 'port')) == 6000
            and service.get(('service', 'protocol')) == IPPROTO_TCP
        ):
            break
        buffer.append(service)
    else:
        raise KeyError('service not found')
    print(buffer)
