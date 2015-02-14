#!/bin/bash

#
# This hack is caused by the bad design of the pyroute2 root
# re-imports. To override a common variable, we have to import
# `common` module; but thus we import all the modules, proxied
# by the root module.
#
# But the variable must be overrode before all other modules
# are imported. So, switch autoimport off in order to override
# the variable
#
# Please note, that with PYROUTE2_NO_AUTOIMPORT you can not
# use `from pyroute2 import IPRoute` anymore -- you should
# specify full paths, `from pyroute2.iproute import IPRoute`
# etc.
#
export PYROUTE2_NO_AUTOIMPORT="True"
exec python ./custom_socket_base.py
