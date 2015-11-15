Examples
========

This directory contains code examples, written in the form of scripts.
An example script, placed here, *must* meet following requirements:

* Able to run as a script w/o any command line parameters.
* Able to be imported as a module, running the code at import time.
* An example script *must* clean up after itself all it created.
* All allocated resources *must* be released.
* Significant exceptions *must* be raised further, but *after* cleanup.
* There *must* be corresponding test case in `tests/test_examples.py`.

The goal is to keep examples tested and working with the current code base;
to increase code coverage; to drop the dead code on time. Actually, thus
examples become a part of the integration testing.
