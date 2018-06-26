from pyroute2.netlink import nla
from pyroute2.netlink import NLA_F_NESTED

class option(nla):
    nla_flags = NLA_F_NESTED
    nla_map = (('TCA_IPSET_UNSPEC', 'none'),
               ('TCA_IPSET_PARMS', 'tcf_ipset_parms'),
               )

    class tcf_ipset_parms(nla):
        fields = (('TCA_ID', 'H'),
                  ('TCA_EMATCH_TREE_HDR', 'tcf_tree_header'),
                  ('TCA_CLASS_ID', 'I'),
                  )

        class tcf_tree_header(nla):
            fields = (('TCA_EMATCH_TREE_LIST', 'tcf_tree_list'),
                      )

            class tcf_tree_list(nla):
                fields = (('TCA_UNK1', 'I'),
                          ('TCA_UNK2', 'I'),
                          ('TCA_UNK3', 'I'),
                          ('TCA_IPSET_INDEX', 'B'),
                          ('TCA_IPSET_UNK', 'B'),
                          ('TCA_IPSET_DIMENSION', 'B'),
                          ('TCA_IPSET_MODE', 'B'),
                          ('TCA_IPSET_UNK2', 'I'),
                          )
