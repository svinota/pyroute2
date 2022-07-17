from setup import lab
from task import IPRoute

ipr = lab.registry[0]
if not isinstance(ipr, IPRoute):
    raise AssertionError('expected IPRoute instance')

ipr.get_links.assert_called()
ipr.close.assert_called_once()
