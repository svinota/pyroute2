from setup import lab
from task import IPRoute

ipr = lab.registry[0]
if not isinstance(ipr, IPRoute):
    raise AssertionError('expected IPRoute instance')

if not ipr.close.called:
    print('\nWARNING: it is recommended to close IPRoute instances')
