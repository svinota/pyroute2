import json
import errno
from subprocess import check_output, CalledProcessError
from nose.plugins.skip import SkipTest

from pyroute2 import netns
from pyroute2.nftables.main import NFTables
from pyroute2.nftables.rule import NFTRule

from utils import require_user

NFT_BIN_PATH = "nft"
NS_NAME = 'pyroute2_test_nftable'


class NFTables_test(object):

    def setup(self):
        require_user('root')
        try:
            netns.create(NS_NAME)
        except OSError as e:
            if e.errno == errno.EEXIST:
                netns.remove(NS_NAME)
                netns.create(NS_NAME)
            else:
                raise
        try:
            check_output([NFT_BIN_PATH, "-f", "nftables.ruleset"])
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise SkipTest("You must install nftables for the test")
            else:
                raise

    def teardown(self):
        netns.remove(NS_NAME)

    def test_export_json(self):
        try:
            nft_res = json.loads(
                check_output([NFT_BIN_PATH, "export", "json"]))
        except CalledProcessError:
            raise SkipTest(
                "Please install nft compiled with --with-json option")
        nft_res = [e['rule'] for e in nft_res['nftables'] if 'rule' in e]
        my_res = []
        for r in NFTables(nfgen_family=0).get_rules():
            my_res.append(NFTRule.from_netlink(r).to_dict())
        assert my_res == nft_res
