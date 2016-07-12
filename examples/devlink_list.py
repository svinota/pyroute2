from pyroute2 import DL

dl = DL()
for q in dl.get_dump():
    print('%s\t%s' % (q.get_attr('DEVLINK_ATTR_BUS_NAME'),
                      q.get_attr('DEVLINK_ATTR_DEV_NAME')))
dl.close()
