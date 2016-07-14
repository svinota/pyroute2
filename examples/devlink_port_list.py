from pyroute2 import DL

dl = DL()
for q in dl.get_port_dump():
    print('%s\t%s\t%u' % (q.get_attr('DEVLINK_ATTR_BUS_NAME'),
                          q.get_attr('DEVLINK_ATTR_DEV_NAME'),
                          q.get_attr('DEVLINK_ATTR_PORT_INDEX')))
dl.close()
