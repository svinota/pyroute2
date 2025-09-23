import json
import subprocess


def test_pcap_rtnl():
    decoder = subprocess.Popen(
        [
            "pyroute2-decoder",
            "-c",
            "pyroute2/netlink/rtnl/marshal.MarshalRtnl",
            "-d",
            "test_decoder/nl0.pcap",
            "-m",
            "ll_header{family=0}",
        ],
        stdout=subprocess.PIPE,
    )
    dump = json.loads(decoder.communicate()[0])
    decoder.wait()
    with open("test_decoder/nl0.json", 'r') as f:
        ref = json.load(f)
    assert len(ref) == len(dump)
    for i in range(len(ref)):
        assert ref[i]["pcap header"] == dump[i]["pcap header"]
        assert ref[i]["message class"] == dump[i]["message class"]


def test_pcap_ipvs():
    decoder = subprocess.Popen(
        [
            "pyroute2-decoder",
            "-c",
            "pyroute2/netlink/generic/ipvs.ipvsmsg",
            "-d",
            "test_decoder/nl0.pcap",
            "-m",
            (
                "ll_header{family=16}"
                " AND data{fmt='H', offset=4, value=37}"
                " AND data{fmt='B', offset=16, value=1}"
            ),
        ],
        stdout=subprocess.PIPE,
    )
    dump = json.loads(decoder.communicate()[0])
    decoder.wait()
    assert len(dump) == 1
    assert dump[0]["data"]["cmd"] == 1
    assert dump[0]["data"]["header"]["type"] == 37
    assert dump[0]["link layer header"].find("family=16") > 0
    assert dump[0]["data"]["attrs"][0][0] == "IPVS_CMD_ATTR_SERVICE"
