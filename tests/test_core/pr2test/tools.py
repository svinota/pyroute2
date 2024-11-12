import json
import subprocess
import time
from collections import namedtuple
from functools import reduce

ip_object_filter = namedtuple('ip_object_filter', ('query', 'value'))


def fix_list(value):
    if not isinstance(value, list):
        value = [value]
    return value


def wait_for_ip_object(cmd, filters, timeout, retry):
    timeout_ns = timeout * 1_000_000_000
    ts = time.time_ns()
    found = False

    while not found:
        check = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if check.returncode != 0:
            break

        dump = json.loads(check.stdout)
        found = False
        for node in dump:
            if all(
                (
                    flt.value
                    in reduce(
                        lambda x, y: (
                            fix_list(x.get(y, {}))
                            if isinstance(x, dict)
                            else [z.get(y, {}) for z in x]
                        ),
                        [node] + flt.query.lstrip('.').split('.'),
                    )
                    for flt in filters
                )
            ):
                found = True
                break

        if found or (time.time_ns() > ts + timeout_ns):
            break

        time.sleep(retry)
    return found


def address_exists(address, ifname=None, timeout=1, retry=0.2):
    filters = [ip_object_filter(query='.addr_info.local', value=address)]
    ifspec = ['dev', ifname] if ifname is not None else []
    return wait_for_ip_object(
        ['ip', '-json', 'addr', 'show'] + ifspec, filters, timeout, retry
    )


def interface_exists(ifname, netns=None, timeout=1, retry=0.2):
    filters = [ip_object_filter(query='.ifname', value=ifname)]
    return wait_for_ip_object(
        ['ip', '-json', 'link', 'show'], filters, timeout, retry
    )


def qdisc_exists(
    ifname, handle, default=None, netns=None, timeout=1, retry=0.2
):
    filters = [ip_object_filter(query='.handle', value=handle)]
    if default is not None:
        filters.append(
            ip_object_filter(query='.options.default', value=default)
        )
    return wait_for_ip_object(
        ['tc', '-json', 'qdisc', 'show', 'dev', ifname],
        filters,
        timeout,
        retry,
    )
