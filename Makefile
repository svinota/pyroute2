##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#

##
# Pyroute version and release
#
version ?= 0.5
release := $(shell git describe | sed 's/-[^-]*$$//;s/-/.post/')
##
# Python-related configuration
#
python ?= python
nosetests ?= nosetests
flake8 ?= flake8
setuplib ?= setuptools
epydoc ?= epydoc
pytest ?= pytest
##
# Python -W flags:
#
#  ignore  -- completely ignore
#  default -- default action
#  all     -- print all warnings
#  module  -- print the first warning occurence for a module
#  once    -- print each warning only once
#  error   -- fail on any warning
#
#  Would you like to know more? See man 1 python
#
wlevel ?= once

##
# Other options
#
# root      -- install root (default: platform default)
# lib       -- lib installation target (default: platform default)
# coverage  -- whether to produce html coverage (default: false)
# pdb       -- whether to run pdb on errors (default: false)
# module    -- run only the specified test module (default: run all)
#
ifdef root
	override root := "--root=${root}"
endif

ifdef lib
	override lib := "--install-lib=${lib}"
endif

all:
	@echo targets:
	@echo
	@echo \* clean -- clean all generated files
	@echo \* docs -- generate project docs \(requires sphinx\)
	@echo \* test -- run functional tests \(see README.make.md\)
	@echo \* install -- install lib into the system
	@echo \* develop -- run \"setup.py develop\" \(requires setuptools\)
	@echo

clean: clean-version
	@rm -rf dist build MANIFEST
	@rm -f README.md
	@rm -f docs-build.log
	@rm -f docs/general.rst
	@rm -f docs/changelog.rst
	@rm -f docs/makefile.rst
	@rm -f docs/report.rst
	@rm -rf docs/api
	@rm -rf docs/html
	@rm -rf docs/doctrees
	@[ -z "${keep_coverage}" ] && rm -f  tests/.coverage ||:
	@rm -rf tests/htmlcov
	@[ -z "${keep_coverage}" ] && rm -rf tests/cover ||:
	@rm -rf tests/examples
	@rm -rf tests/bin
	@rm -rf tests/pyroute2
	@rm -f  tests/*xml
	@rm -f  tests/tests.json
	@rm -f  tests/tests.log
	@rm -rf pyroute2.egg-info
	@rm -rf tests-workspaces
	@rm -f python-pyroute2.spec
	@rm -f pyroute2/config/version.py
	@find pyroute2 -name "*pyc" -exec rm -f "{}" \;
	@find pyroute2 -name "*pyo" -exec rm -f "{}" \;

setup.ini:
	@awk 'BEGIN {print "[setup]\nversion=${version}\nrelease=${release}\nsetuplib=${setuplib}"}' >setup.ini
	@awk 'BEGIN {print "__version__ = \"${release}\""}' >pyroute2/config/version.py

clean-version:
	@rm -f setup.ini

force-version: clean-version update-version

update-version: setup.ini

docs: force-version README.md
	@cp README.rst docs/general.rst
	@cp README.make.md docs/makefile.rst
	@cp README.report.md docs/report.rst
	@cp CHANGELOG.md docs/changelog.rst
	@[ -f docs/_templates/private.layout.html ] && ( \
	    mv -f docs/_templates/layout.html docs/_templates/layout.html.orig; \
		cp docs/_templates/private.layout.html docs/_templates/layout.html; ) ||:
	@export PYTHONPATH=`pwd`; \
		make -C docs html >docs-build.log 2>&1 || export FAIL=true ; \
		[ -f docs/_templates/layout.html.orig ] && ( \
			mv -f docs/_templates/layout.html.orig docs/_templates/layout.html; ) ||: ;\
		unset PYTHONPATH ;\
		[ -z "$$FAIL" ] || false

epydoc: docs
	${epydoc} -v \
		--no-frames \
		-o docs/api \
		--html \
		--graph all \
		--fail-on-docstring-warning \
		pyroute2/

check_parameters:
	@if [ ! -z "${skip_tests}" ]; then \
		echo "'skip_tests' is deprecated, use 'skip=...' instead"; false; fi

test: check_parameters
	@export PYTHON=${python}; \
		export NOSE=${nosetests}; \
		export FLAKE8=${flake8}; \
		export WLEVEL=${wlevel}; \
		export SKIP_TESTS=${skip}; \
		export PDB=${pdb}; \
		export COVERAGE=${coverage}; \
		export MODULE=${module}; \
		export LOOP=${loop}; \
		export REPORT=${report}; \
		export WORKER=${worker}; \
		export WORKSPACE=${workspace}; \
		./tests/run.sh

pytest: check_parameters
	@export PYTHON=${python}; \
		export PYTEST=${pytest}; \
		export FLAKE8=${flake8}; \
		export WLEVEL=${wlevel}; \
		export SKIP_TESTS=${skip}; \
		export PDB=${pdb}; \
		export COVERAGE=${coverage}; \
		export MODULE=${module}; \
		export LOOP=${loop}; \
		export REPORT=${report}; \
		export WORKER=${worker}; \
		export WORKSPACE=${workspace}; \
		export PYROUTE2_TEST_DBNAME=${dbname}; \
		./tests/run_pytest.sh

test-platform:
	@${python} -c "\
import logging;\
logging.basicConfig();\
from pyroute2.config.test_platform import TestCapsRtnl;\
from pprint import pprint;\
pprint(TestCapsRtnl().collect())"

upload: clean force-version docs
	${python} setup.py sdist
	${python} -m twine upload --repository-url https://upload.pypi.org/legacy/ dist/*

dist: force-version docs
	@${python} setup.py sdist >/dev/null 2>&1

README.md:
	@cat README.rst | ${python} ./docs/conv.py >README.md

install: clean force-version README.md
	${python} setup.py install ${root} ${lib}

# in order to get it working, one should install pyroute2
# with setuplib=setuptools, otherwise the project files
# will be silently left not uninstalled
uninstall: clean
	${python} -m pip uninstall pyroute2

develop: setuplib = "setuptools"
develop: clean force-version
	${python} setup.py develop
