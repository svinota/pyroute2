from setup import lab
from task import IPRoute

if len(lab.registry) != 1:
    raise AssertionError('expected exactly one IPRoute instance')
if not isinstance(lab.registry[0], IPRoute):
    raise AssertionError('expected IPRoute instance')

ipr = lab.registry[0]
ipr.get_addr.assert_called()
ipr.close.assert_called_once()
