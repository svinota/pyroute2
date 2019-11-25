from pyroute2.netlink import nla


# Defines from sch_ckae.c
CAKE_FLAG_OVERHEAD = 0
CAKE_FLAG_AUTORATE_INGRESS = 1
CAKE_FLAG_INGRESS = 2
CAKE_FLAG_WASH = 3
CAKE_FLAG_SPLIT_GSO = 4
CAKE_FLAG_STORE_MARK = 5
CAKE_FLAG_SCE = 6


class options(nla):
    nla_map = (('TCA_CAKE_BASE_UNSPEC', 'none'),
               ('TCA_CAKE_BASE_RATE64', 'uint64'),
               ('TCA_CAKE_DIFFSERV_MODE', 'uint32'),
               ('TCA_CAKE_ATM', 'uint32'),
               ('TCA_CAKE_FLOW_MODE', 'uint32'),
               ('TCA_CAKE_OVERHEAD', 'uint32'),
               ('TCA_CAKE_RTT', 'uint32'),
               ('TCA_CAKE_TARGET', 'uint32'),
               ('TCA_CAKE_AUTORATE', 'uint32'),
               ('TCA_CAKE_MEMORY', 'uint32'),
               ('TCA_CAKE_NAT', 'uint32'),
               ('TCA_CAKE_RAW', 'uint32'),
               ('TCA_CAKE_WASH', 'uint32'),
               ('TCA_CAKE_MPU', 'uint32'),
               ('TCA_CAKE_INGRESS', 'uint32'),
               ('TCA_CAKE_ACK_FILTER', 'uint32'),
               ('TCA_CAKE_FWMARK', 'uint32'),
               ('TCA_CAKE_FWMARK_STORE', 'uint32'),
               ('TCA_CAKE_SCE', 'uint32'),
               )
