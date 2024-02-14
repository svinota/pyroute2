import errno
import shutil
import subprocess

from pyroute2.netlink import nlmsg
from pyroute2.netlink.exceptions import NetlinkError


class probe_msg(nlmsg):
    '''
    Fake message type to represent network probe info.

    This is a prototype, the NLA layout is subject to change without
    notification.
    '''

    __slots__ = ()
    prefix = 'PROBE_'

    fields = (('family', 'B'), ('proto', 'B'), ('port', 'H'), ('dst_len', 'I'))

    nla_map = (
        ('PROBE_UNSPEC', 'none'),
        ('PROBE_KIND', 'asciiz'),
        ('PROBE_STDOUT', 'asciiz'),
        ('PROBE_STDERR', 'asciiz'),
        ('PROBE_SRC', 'target'),
        ('PROBE_DST', 'target'),
        ('PROBE_NUM', 'uint8'),
        ('PROBE_TIMEOUT', 'uint8'),
    )


def proxy_newprobe(msg, nl):
    num = msg.get('num')
    timeout = msg.get('timeout')
    dst = msg.get('dst')
    kind = msg.get('kind')

    if kind.endswith('ping'):
        args = [
            shutil.which(kind),
            '-c',
            f'{num}',
            '-W',
            f'{timeout}',
            f'{dst}',
        ]
        if args[0] is None:
            raise NetlinkError(errno.ENOENT, 'probe not found')

        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            out, err = process.communicate(timeout=timeout)
            if out:
                msg['attrs'].append(['PROBE_STDOUT', out])
            if err:
                msg['attrs'].append(['PROBE_STDERR', err])
        except subprocess.TimeoutExpired:
            process.terminate()
            raise NetlinkError(errno.ETIMEDOUT, 'timeout expired')
        finally:
            process.stdout.close()
            process.stderr.close()
            return_code = process.wait()
        if return_code != 0:
            raise NetlinkError(errno.EHOSTUNREACH, 'probe failed')
    else:
        raise NetlinkError(errno.ENOTSUP, 'probe type not supported')
    msg.reset()
    msg.encode()
    return {'verdict': 'return', 'data': msg.data}
