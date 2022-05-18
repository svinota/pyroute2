def _test_ntables(self):
    setA = set(
        filter(
            lambda x: x is not None,
            [
                x.get_attr('NDTA_PARMS').get_attr('NDTPA_IFINDEX')
                for x in self.ip.get_ntables()
            ],
        )
    )
    setB = set([x['index'] for x in self.ip.get_links()])
    assert setA == setB
