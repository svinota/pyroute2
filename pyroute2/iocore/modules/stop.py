import uuid
from pyroute2.netlink import NLMSG_TRANSPORT
from pyroute2.netlink import IPRCMD_ACK
from pyroute2.netlink import IPRCMD_STOP
from pyroute2.netlink.generic import envmsg
from pyroute2.iocore import NLT_CONTROL
from pyroute2.iocore import NLT_RESPONSE
from pyroute2.iocore.utils import access


target = IPRCMD_STOP
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    # Last 'hello'
    rsp['cmd'] = IPRCMD_ACK
    rsp.encode()
    ne = envmsg()
    ne['header']['sequence_number'] = env['header']['sequence_number']
    ne['header']['pid'] = env['header']['pid']
    ne['header']['type'] = NLMSG_TRANSPORT
    ne['header']['flags'] = NLT_CONTROL | NLT_RESPONSE
    ne['dst'] = env['src']
    ne['src'] = env['dst']
    ne['id'] = uuid.uuid4().bytes
    ne['dport'] = env['sport']
    ne['sport'] = env['dport']
    ne['attrs'] = [['IPR_ATTR_CDATA', rsp.buf.getvalue()]]
    ne.encode()
    sock.send(ne.buf.getvalue())
    # Stop iothread -- shutdown sequence
    return broker.shutdown()
