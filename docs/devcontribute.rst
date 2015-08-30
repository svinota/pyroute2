.. devcontribute:

Project contribution guide
==========================

To contribute the code to the project, you can use the
github instruments: issues and pull-requests. See more
on the project github page: https://github.com/svinota/pyroute2

Requirements
++++++++++++

The code should comply with some requirements:

* the library must work on Python >= 2.6 and 3.2.
* the code must strictly comply with PEP8 (use `flake8`)
* the `ctypes` usage must not break the library on SELinux

Testing
+++++++

To perform code tests, run `make test`. Details about
the makefile parameters see in `README.make.md`.

Links
+++++

* flake8: https://pypi.python.org/pypi/flake8
* vim-flake8: https://github.com/nvie/vim-flake8
* nosetests: http://nose.readthedocs.org/en/latest/
