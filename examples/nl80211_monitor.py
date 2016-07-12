from pyroute2 import IW


# register IW to get all the messages
iw = IW(groups=0xfff)
print(iw.get())
iw.close()
