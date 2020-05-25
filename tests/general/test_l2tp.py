import os
import uuid

from utils import allocate_network
from utils import free_network
from utils import require_user
from utils import skip_if_not_supported

from pyroute2 import L2tp
from pyroute2 import NDB
from pyroute2.common import uifname


class TestL2tp:
    @skip_if_not_supported
    def setup(self):
        require_user("root")
        self.l2tp = L2tp()
        self.log_id = str(uuid.uuid4())
        self.ndb = NDB(
            log="../ndb-%s-%s.log" % (os.getpid(), self.log_id),
            rtnl_debug=True,
        )
        self.netif = uifname()
        self.l2tpeth0 = uifname()
        self.localnet = allocate_network()
        self.remotenet = allocate_network()
        self.localrange = [str(x) for x in self.localnet]
        self.remoterange = [str(x) for x in self.remotenet]
        # create the "network" interface
        (
            self.ndb.interfaces.create(ifname=self.netif, kind="dummy")
                .set("state", "up")
                .add_ip("%s/24" % (self.localrange[1]))
                .commit()
        )

    def teardown(self):
        with NDB() as ndb:
            (ndb.interfaces[self.netif].remove().commit())
        self.ndb.close()
        free_network(self.localnet)
        free_network(self.remotenet)

    def test_1_create_tunnel(self):
        self.l2tp.create_tunnel(
            tunnel_id=2324,
            peer_tunnel_id=2425,
            remote=self.remoterange[1],
            local=self.localrange[1],
            udp_dport=32000,
            udp_sport=32000,
            encap="udp",
        )

        tunnel = self.l2tp.get_tunnel(tunnel_id=2324)
        assert tunnel[0].get_attr("L2TP_ATTR_CONN_ID") == 2324
        assert tunnel[0].get_attr("L2TP_ATTR_PEER_CONN_ID") == 2425
        assert tunnel[0].get_attr("L2TP_ATTR_IP_DADDR") == self.remoterange[1]
        assert tunnel[0].get_attr("L2TP_ATTR_IP_SADDR") == self.localrange[1]
        assert tunnel[0].get_attr("L2TP_ATTR_UDP_DPORT") == 32000
        assert tunnel[0].get_attr("L2TP_ATTR_UDP_SPORT") == 32000
        assert tunnel[0].get_attr("L2TP_ATTR_ENCAP_TYPE") == 0  # 0 == UDP
        assert tunnel[0].get_attr("L2TP_ATTR_DEBUG") == 0

    def test_2_create_session(self):
        self.l2tp.create_session(
            tunnel_id=2324,
            session_id=3435,
            peer_session_id=3536,
            ifname=self.l2tpeth0,
        )

        session = self.l2tp.get_session(tunnel_id=2324, session_id=3435)
        assert session[0].get_attr("L2TP_ATTR_SESSION_ID") == 3435
        assert session[0].get_attr("L2TP_ATTR_PEER_SESSION_ID") == 3536
        assert session[0].get_attr("L2TP_ATTR_DEBUG") == 0

    def test_3_modify_session(self):
        self.l2tp.modify_session(tunnel_id=2324, session_id=3435, debug=True)
        session = self.l2tp.get_session(tunnel_id=2324, session_id=3435)
        assert session[0].get_attr("L2TP_ATTR_DEBUG") == 1

    def test_4_modify_tunnel(self):
        self.l2tp.modify_tunnel(tunnel_id=2324, debug=True)
        tunnel = self.l2tp.get_tunnel(tunnel_id=2324)
        assert tunnel[0].get_attr("L2TP_ATTR_DEBUG") == 1

    def test_5_destroy_session(self):
        self.l2tp.delete_session(tunnel_id=2324, session_id=3435)
        assert not self.l2tp.get_session(tunnel_id=2324, session_id=3435)

    def test_6_destroy_tunnel(self):
        self.l2tp.delete_tunnel(tunnel_id=2324)
        assert not self.l2tp.get_tunnel(tunnel_id=2324)
