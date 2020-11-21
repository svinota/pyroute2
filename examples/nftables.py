#!/usr/bin/env python3

from pyroute2.nftables.main import NFTables


# nfgen_family 0 == inet
def show_nftables(family: int = 0) -> None:
    nft = NFTables(nfgen_family=family)
    tables = nft.get_tables()
    chains = nft.get_chains()
    rules = nft.get_rules()

    print("Tables:")
    print(tables)
    print("\nChains:")
    print(chains)
    print("\nRules:")
    for rule in rules:
        print(rule, type(rule))


show_nftables(0)
