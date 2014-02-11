import socket
from pyroute2.iocore.utils import get_socket
from pyroute2.netlink import IPRCMD_SERVE
from pyroute2.iocore.utils import access


target = IPRCMD_SERVE
level = access.ADMIN


def command(broker, sock, env, cmd, rsp):
    url = cmd.get_attr('IPR_ATTR_HOST')
    key = cmd.get_attr('IPR_ATTR_SSL_KEY')
    cert = cmd.get_attr('IPR_ATTR_SSL_CERT')
    ca = cmd.get_attr('IPR_ATTR_SSL_CA')
    (new_sock, addr) = get_socket(url, server=True,
                                  key=key,
                                  cert=cert,
                                  ca=ca)
    new_sock.setsockopt(socket.SOL_SOCKET,
                        socket.SO_REUSEADDR, 1)
    new_sock.bind(addr)
    if new_sock.type == socket.SOCK_STREAM:
        new_sock.listen(16)
        broker.ioloop.register(new_sock,
                               broker.handle_connect)
    else:
        broker.ioloop.register(new_sock,
                               broker.route,
                               defer=True)
    broker.servers.add(new_sock)
    broker._rlist.add(new_sock)
    broker.sockets[url] = new_sock
