##
# This modules is only to provide the compatibility with pyroute2 0.6.x
import sys

# load pyroute2 entry points
import pyroute2  # noqa: F401

# alias every `pyroute2` entry, in addition to the block above
#
# Bug-Url: https://github.com/svinota/pyroute2/issues/913
#
for key, value in list(sys.modules.items()):
    if key.startswith("pyroute2."):
        sys.modules[key.replace("pyroute2", "pr2modules")] = value
