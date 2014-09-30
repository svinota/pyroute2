import io
import errno
import uuid
from socket import SOL_SOCKET
from socket import SO_SNDBUF
from socket import SO_RCVBUF
from pyroute2.netlink import IPRCMD_CONNECT
from pyroute2.netlink import NETLINK_ROUTE
from pyroute2.netlink import envmsg
from pyroute2.netlink import mgmtmsg
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.rtnl import RtnlSocket
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
    pid = cmd.get_attr('IPR_ATTR_PID')
    sndbuf = cmd.get_attr('IPR_ATTR_SNDBUF', 32768)
    rcvbuf = cmd.get_attr('IPR_ATTR_RCVBUF', 1024 * 1024)

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
        family = int(res[1])
        if family == NETLINK_ROUTE:
            new_sock = RtnlSocket()
        else:
            new_sock = NetlinkSocket(int(res[1]), pid=pid)
        new_sock.setsockopt(SOL_SOCKET, SO_SNDBUF, sndbuf)
        new_sock.setsockopt(SOL_SOCKET, SO_RCVBUF, rcvbuf)
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
        broker.ioloop.register(new_sock, route, defer=True)
        if hasattr(new_sock, 'bypass'):
            broker.ioloop.register(new_sock.bypass, route, defer=True,
                                   proxy=new_sock)
    except Exception as e:
        if e.errno != errno.EEXIST:
            raise e
