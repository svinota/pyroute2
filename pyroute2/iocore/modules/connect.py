import io
import errno
import uuid
from pyroute2.netlink import NetlinkSocket
from pyroute2.netlink import IPRCMD_CONNECT
from pyroute2.netlink.generic import envmsg
from pyroute2.netlink.generic import mgmtmsg
from pyroute2.iocore.utils import get_socket
from pyroute2.iocore.utils import access
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


target = IPRCMD_CONNECT
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    key = cmd.get_attr('IPR_ATTR_SSL_KEY')
    cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
    ca = cmd.get_attr('IPR_ATTR_SSL_CA')

    target = urlparse.urlparse(url)
    peer = broker.addr
    remote = False
    established = False
    uid = str(uuid.uuid4())

    route = broker.route

    if url in broker.providers:
        new_sock = broker.providers[url]
        established = True
        gate = lambda d, s:\
            new_sock.send(broker.gate_forward(d, s))

    elif target.scheme == 'netlink':
        res = target.path.split("/")
        new_sock = NetlinkSocket(int(res[1]))
        new_sock.bind(int(res[2]))
        gate = lambda d, s:\
            new_sock.sendto(broker.gate_untag(d, s), (0, 0))
        route = broker.route_netlink

    elif target.scheme == 'udp':
        (new_sock, addr) = get_socket(url, server=False)
        gate = lambda d, s:\
            new_sock.sendto(broker.gate_forward(d, s), addr)
        remote = True

    else:
        (new_sock, addr) = get_socket(url,
                                      server=False,
                                      key=key,
                                      cert=cert,
                                      ca=ca)
        try:
            new_sock.connect(addr)
        except Exception:
            new_sock.close()
            raise
        remote = True
        # stream sockets provide the peer announce
        buf = io.BytesIO()
        buf.length = buf.write(new_sock.recv(16384))
        buf.seek(0)
        msg = envmsg(buf)
        msg.decode()
        buf = io.BytesIO()
        buf.length = buf.write(msg.get_attr('IPR_ATTR_CDATA'))
        buf.seek(0)
        msg = mgmtmsg(buf)
        msg.decode()
        peer = msg.get_attr('IPR_ATTR_ADDR')

        gate = lambda d, s:\
            new_sock.send(broker.gate_forward(d, s))

    port = broker.alloc_addr()
    link = broker.register_link(uid=uid,
                                port=port,
                                sock=new_sock,
                                established=established,
                                remote=remote)
    link.gate = gate
    broker.discover[target.path] = port
    rsp['attrs'].append(['IPR_ATTR_UUID', uid])
    rsp['attrs'].append(['IPR_ATTR_ADDR', peer])
    try:
        broker.ioloop.register(new_sock, route,
                               defer=True)
    except Exception as e:
        if e.errno != errno.EEXIST:
            raise e
