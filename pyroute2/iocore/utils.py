import ssl
import socket
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class access(object):
    ANY = 0xffffffff
    USER = 0x1
    ADMIN = 0x2


def get_socket(url, server=False,
               key=None, cert=None, ca=None):
    assert url[:6] in ('udp://', 'tcp://', 'ssl://', 'tls://') or \
        url[:11] in ('unix+ssl://', 'unix+tls://') or url[:7] == 'unix://'
    target = urlparse.urlparse(url)
    hostname = target.hostname or ''
    use_ssl = False
    ssl_version = 2

    if target.scheme[:4] == 'unix':
        if hostname and hostname[0] == '\0':
            address = hostname
        else:
            address = ''.join((hostname, target.path))
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    elif target.scheme[:3] == 'udp':
        address = (socket.gethostbyname(hostname), target.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
        address = (socket.gethostbyname(hostname), target.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if target.scheme.find('ssl') >= 0:
        ssl_version = ssl.PROTOCOL_SSLv3
        use_ssl = True

    if target.scheme.find('tls') >= 0:
        ssl_version = ssl.PROTOCOL_TLSv1
        use_ssl = True

    if use_ssl:

        assert key and cert and ca

        sock = ssl.wrap_socket(sock,
                               keyfile=key,
                               certfile=cert,
                               ca_certs=ca,
                               server_side=server,
                               cert_reqs=ssl.CERT_REQUIRED,
                               ssl_version=ssl_version)
    return (sock, address)
