import json
import subprocess
import time


def interface_exists(ifname, netns=None, timeout=1, retry=0.2):
    timeout_ns = timeout * 1_000_000_000
    ts = time.time_ns()
    found = False

    while True:
        check = subprocess.run(
            ['ip', '-json', 'link', 'show'], stdout=subprocess.PIPE
        )
        result = json.loads(check.stdout)
        found = False
        for link in result:
            if link['ifname'] == ifname:
                found = True

        if time.time_ns() > ts + timeout_ns:
            break

    return found
