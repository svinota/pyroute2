from setup import lab
from task import IPRoute

assert len(lab.registry) == 1
assert isinstance(lab.registry[0], IPRoute)

ipr = lab.registry[0]
ipr.get_links.assert_called()
ipr.close.assert_called_once()
