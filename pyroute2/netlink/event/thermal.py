'''
TODO: add THERMAL_GENL_ATTR_EVENT structure
'''
from pyroute2.netlink import genlmsg
from pyroute2.netlink.event import EventSocket
from pyroute2.netlink.nlsocket import Marshal

THERMAL_GENL_CMD_UNSPEC = 0
THERMAL_GENL_CMD_EVENT = 1


class thermal_msg(genlmsg):
    nla_map = (
        ('THERMAL_GENL_ATTR_UNSPEC', 'none'),
        ('THERMAL_GENL_ATTR_TZ', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_ID', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TEMP', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TRIP', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TRIP_ID', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TRIP_TYPE', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TRIP_TEMP', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_TRIP_HYST', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_MODE', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_NAME', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_CDEV_WEIGHT', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_GOV', 'hex'),
        ('THERMAL_GENL_ATTR_TZ_GOV_NAME', 'hex'),
        ('THERMAL_GENL_ATTR_CDEV', 'hex'),
        ('THERMAL_GENL_ATTR_CDEV_ID', 'hex'),
        ('THERMAL_GENL_ATTR_CDEV_CUR_STATE', 'hex'),
        ('THERMAL_GENL_ATTR_CDEV_MAX_STATE', 'hex'),
        ('THERMAL_GENL_ATTR_CDEV_NAME', 'hex'),
        ('THERMAL_GENL_ATTR_GOV_NAME', 'hex'),
        ('THERMAL_GENL_ATTR_CPU_CAPABILITY', 'hex'),
        ('THERMAL_GENL_ATTR_CPU_CAPABILITY_ID', 'hex'),
        ('THERMAL_GENL_ATTR_CPU_CAPABILITY_PERFORMANCE', 'hex'),
        ('THERMAL_GENL_ATTR_CPU_CAPABILITY_EFFICIENCY', 'hex'),
    )


class MarshalThermalEvent(Marshal):
    msg_map = {
        THERMAL_GENL_CMD_UNSPEC: thermal_msg,
        THERMAL_GENL_CMD_EVENT: thermal_msg,
    }


class ThermalEventSocket(EventSocket):
    marshal_class = MarshalThermalEvent
    genl_family = 'thermal'
