import time

from pyroute2.netlink.nfnetlink.nftsocket import NFPROTO_IPV4
from pyroute2.nftables.main import NFTables
from pyroute2.nftables.main import NFTSetElem


def test_ipv4_addr_set():
    with NFTables(nfgen_family=NFPROTO_IPV4) as nft:
        nft.table("add", name="filter")
        my_set = nft.sets("add", table="filter", name="test0", key_type="ipv4_addr",
                          comment="my test set", timeout=0)

        # With str
        nft.set_elems(
            "add",
            table="filter",
            set="test0",
            elements={"10.2.3.4", "10.4.3.2"},
        )

        # With NFTSet & NFTSetElem classes
        nft.set_elems(
            "add",
            set=my_set,
            elements={NFTSetElem(value="9.9.9.9", timeout=1000)},
        )

        try:
            assert {e.value for e in nft.set_elems("get", table="filter", set="test0")} == {
                "10.2.3.4",
                "10.4.3.2",
                "9.9.9.9",
            }
            assert nft.sets("get", table="filter", name="test0").comment == b"my test set"

            time.sleep(1.2)
            # timeout for elem 9.9.9.9 (1000ms)
            assert {e.value for e in nft.set_elems("get", table="filter", set="test0")} == {
                "10.2.3.4",
                "10.4.3.2",
            }
        finally:
            nft.sets("del", table="filter", name="test0")
            nft.table("del", name="filter")


def main():
    test_ipv4_addr_set()


if __name__ == "__main__":
    main()
