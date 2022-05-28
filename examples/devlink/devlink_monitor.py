from pyroute2.devlink import DL


dl = DL(groups=~0)
print(dl.get())
dl.close()
