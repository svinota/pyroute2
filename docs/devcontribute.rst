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

It would be good to have the code covered with tests.
The project now uses `nosetests` for this purpose.

To run the full test cycle on the project, using a specific
python, making html coverage report::

    $ sudo make test python=python3 coverage=html

To run a specific test module::

    $ sudo make test module=test_ipdb:TestExplicit

Please keep in mind, that by default the test cycle starts
with `python -W error`, which means that python will **fail**
in the case of any **warning**. Since some Linux
distributives allow really bad modules to be emerged, you
probably will need to switch this behaviour off using
`wlevel` parameter::

    $ sudo make test wlevel=ignore

Links
+++++

* flake8: https://pypi.python.org/pypi/flake8
* vim-flake8: https://github.com/nvie/vim-flake8
* nosetests: http://nose.readthedocs.org/en/latest/
