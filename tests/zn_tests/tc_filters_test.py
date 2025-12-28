import os
import itertools
import subprocess
import pytest

import pyroute2
from pyroute2 import IPRoute

EXPECTED_PYROUTE2_VERSION = "0.7.10.4"
IFNAME = "zn-tc-test0"
GNV_IFNAME = "zn-tc-gnv0"

CLSACT_INGRESS = 0xFFFFFFF2
CLSACT_EGRESS  = 0xFFFFFFF3

pytestmark = pytest.mark.skipif(
    os.geteuid() != 0,
    reason="Requires root (run: sudo -E pytest -q)",
)


def _run(cmd, check=True):
    return subprocess.run(
        cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def _try_run(cmd):
    return _run(cmd, check=False)


def _print_cmd_result(title, res):
    print(title)
    out = (res.stdout or "").rstrip()
    err = (res.stderr or "").strip()
    if out:
        print(out)
    else:
        print("<none>")
    if err:
        print("stderr:", err)


def tc_show_state(tag):
    print("\n==== TC STATE {} (dev {}) ====".format(tag, IFNAME))

    _print_cmd_result("-- qdisc --", _try_run(["tc", "qdisc", "show", "dev", IFNAME]))
    _print_cmd_result("-- filters ingress --", _try_run(["tc", "filter", "show", "dev", IFNAME, "ingress"]))
    _print_cmd_result("-- filters egress --", _try_run(["tc", "filter", "show", "dev", IFNAME, "egress"]))

    print("================================\n")


def get_interface_index(ipr, interface_name):
    for link in ipr.get_links():
        if link.get_attr("IFLA_IFNAME") == interface_name:
            return link["index"]
    return None


def ensure_clsact(ipr, ifindex):
    try:
        ipr.tc("add", "clsact", ifindex)
    except Exception as e:
        if "File exists" not in str(e):
            raise


def delete_clsact(ipr, ifindex):
    try:
        ipr.tc("del", "clsact", ifindex)
    except Exception as e:
        if "No such file or directory" not in str(e):
            raise



@pytest.fixture(scope="session", autouse=True)
def require_pyroute2_version_once():
    v = pyroute2.__version__
    if v != EXPECTED_PYROUTE2_VERSION:
        pytest.skip("expected pyroute2 {}, got {}".format(EXPECTED_PYROUTE2_VERSION, v))


@pytest.fixture(scope="session")
def ipr():
    ipr_obj = IPRoute()
    try:
        yield ipr_obj
    finally:
        ipr_obj.close()


@pytest.fixture(scope="session", autouse=True)
def dummy_interface():
    _try_run(["ip", "link", "del", IFNAME])
    _run(["ip", "link", "add", IFNAME, "type", "dummy"])
    _run(["ip", "link", "set", IFNAME, "up"])
    try:
        yield
    finally:
        _try_run(["ip", "link", "del", IFNAME])

@pytest.fixture(scope="session", autouse=True)
def gnv_interface():
    """
    Create a dedicated dummy interface that represents gnv0 for the whole test run.
    """
    _try_run(["ip", "link", "del", GNV_IFNAME])

    r = _run(["ip", "link", "add", GNV_IFNAME, "type", "dummy"])
    _run(["ip", "link", "set", GNV_IFNAME, "up"])

    try:
        yield
    finally:
        _try_run(["ip", "link", "del", GNV_IFNAME])

@pytest.fixture(scope="session")
def gnv_ifindex(ipr, gnv_interface):
    idx = get_interface_index(ipr, GNV_IFNAME)
    if idx is None:
        pytest.skip("Geneve dummy interface not found: {}".format(GNV_IFNAME))
    return idx

@pytest.fixture(scope="session")
def ifindex(ipr, dummy_interface):
    idx = get_interface_index(ipr, IFNAME)
    if idx is None:
        pytest.skip("Dummy interface not found: {}".format(IFNAME))
    return idx


@pytest.fixture(scope="session", autouse=True)
def reset_clsact_before_suite(ipr, ifindex, gnv_ifindex):
    tc_show_state("BEFORE SUITE RESET")

    delete_clsact(ipr, ifindex)
    ensure_clsact(ipr, ifindex)

    delete_clsact(ipr, gnv_ifindex)
    ensure_clsact(ipr, gnv_ifindex)

    tc_show_state("AFTER SUITE RESET")



@pytest.fixture(scope="session")
def _prio_counter():
    return itertools.count(100, 100)


@pytest.fixture(scope="function")
def priority(_prio_counter):
    return next(_prio_counter)


@pytest.fixture(scope="function", autouse=True)
def tc_state_before_after_test(request):
    """
    Run with `-s` to see output.
    """
    tc_show_state("BEFORE {}".format(request.node.name))
    try:
        yield
    finally:
        tc_show_state("AFTER {}".format(request.node.name))


def test_flower_ip_port(ipr, ifindex, priority):
    ipr.tc(
        "add-filter",
        "flower",
        ifindex,
        parent=CLSACT_INGRESS,
        prio=priority,
        src_ip='192.168.1.0',
        dst_ip='10.0.0.1',
        ip_proto="tcp",
        dst_port=60,
        actions= [
        {
            'kind': 'gact',
            'action': 'drop',
        }
    ])

def test_flower_ip_cidr_port(ipr, ifindex, priority):
    ipr.tc(
        "add-filter",
        "flower",
        ifindex,
        parent=CLSACT_INGRESS,
        prio=priority,
        src_ip='192.168.1.0/24',
        dst_ip='10.0.0.1/24',
        ip_proto="udp",
        dst_port=68,
        actions= [
        {
            'kind': 'gact',
            'action': 'drop',
        }
    ])


def test_flower_enc_fields(ipr, ifindex, priority):
    ipr.tc(
        "add-filter",
        "flower",
        ifindex,
        parent=CLSACT_INGRESS,
        prio=priority,
        enc_src_ip="192.168.1.0",
        enc_dst_ip="10.0.0.1",
        enc_key_id=124,
        enc_dst_port=6000,
        action=[{"kind": "gact", "action": "drop"}],
    )

def test_flower_geneve_opts(ipr, ifindex, priority):
    ipr.tc(
        "add-filter", "flower", ifindex,
        parent=CLSACT_INGRESS,
        protocol=0x0800,
        prio=priority,
        enc_src_ip='1.1.1.1',
        enc_key_id=1234,
        enc_dst_port=6000,
        geneve_opts="0141:20:00000200",
        action=[
            {"kind": "gact", "action": "drop"}
        ],
    )

@pytest.mark.xfail(reason="ip range is not supported in flower filter")
def test_flower_ip_range(ipr, ifindex, priority):
    ipr.tc(
        "add-filter", "flower", ifindex,
        parent=CLSACT_INGRESS,
        prio=priority,
        src_ip='192.168.1.0-192.168.1.10',
        actions=[{"kind": "gact", "action": "drop"}],
    )