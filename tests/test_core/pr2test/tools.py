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


def class_exists(
    ifname,
    handle,
    kind,
    parent=None,
    root=None,
    netns=None,
    timeout=1,
    retry=0.2,
):
    filters = [
        ip_object_filter(query='.class', value=kind),
        ip_object_filter(query='.handle', value=handle),
    ]
    if root is not None:
        filters.append(ip_object_filter(query='.root', value=root))
    if parent is not None:
        filters.append(ip_object_filter(query='.parent', value=parent))
    return wait_for_ip_object(
        ['tc', '-json', 'class', 'show', 'dev', ifname],
        filters,
        timeout,
        retry,
    )


def filter_exists(
    ifname,
    kind,
    parent=None,
    protocol=None,
    match_value=None,
    match_mask=None,
    netns=None,
    timeout=1,
    retry=0.2,
):
    filters = [ip_object_filter(query='.kind', value=kind)]
    if parent is not None:
        filters.append(ip_object_filter(query='.parent', value=parent))
    if protocol is not None:
        filters.append(ip_object_filter(query='.protocol', value=protocol))
    if match_value is not None:
        filters.append(
            ip_object_filter(query='.options.match.value', value=match_value)
        )
    if match_mask is not None:
        filters.append(
            ip_object_filter(query='.options.match.mask', value=match_mask)
        )
    return wait_for_ip_object(
        ['tc', '-json', 'filter', 'show', 'dev', ifname],
        filters,
        timeout,
        retry,
    )


def qdisc_exists(
    ifname, handle, default=None, rate=None, netns=None, timeout=1, retry=0.2
):
    filters = [ip_object_filter(query='.handle', value=handle)]
    if default is not None:
        filters.append(
            ip_object_filter(query='.options.default', value=default)
        )
    if rate is not None:
        filters.append(ip_object_filter(query='.options.rate', value=rate))
    return wait_for_ip_object(
        ['tc', '-json', 'qdisc', 'show', 'dev', ifname],
        filters,
        timeout,
        retry,
    )
