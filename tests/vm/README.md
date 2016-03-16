VM testing
----------

This framework provides a possibility to test pyroute2
in isolated virtual machines. Why it is important?

* to automate testing on different kernels
* to provide a reasonably safe testing environment

The pyroute2 tests occasionally can damage IP stack of
the system. And if there is not verified git commit
from an external pull request, it is too dangerous to
test it automatically -- the commit can contain a
maleficent code.

The framework address both these safety issues.

How VMs are created
===================

The script `run.sh` iterates all libvirt XML configs
in the `configs` directory and extracts VM name and
disk image path from every config.

If the disk image doesn't exists, the script can
download it by the URL in `urls` file -- if there
exists a record for this VM.

The disk image must be in the qcow2 format and must
contain `init` snapshot. The script automatically
reverts the image to the `init` state every time it
is launched.

The library code is being cloned to `/opt` on the
mounted fs, and then the script copies `rc.local`
which will automatically launch the testing.

After the testing is done, VM will be shut down, and
the script will collect all the logs to the `results`
directory.

Status
======

This is an experimental and unstable part of the
project. Any contributions, hints, issues etc. are
welcome, as usual.
