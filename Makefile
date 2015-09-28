# 	Copyright (c) 2013-2014 Peter V. Saveliev
#
# 	This file is part of pyroute2 project.
#
# 	Pyroute2 is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 2 of the License, or
# 	(at your option) any later version.
#
# 	Pyroute2 is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with PyVFS; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

##
# Pyroute version and release
#
version ?= "0.3"
release := $(shell git describe | sed 's/-[^-]*$$//;s/-/.post/')
##
# Python-related configuration
#
python ?= "python"
nosetests ?= "nosetests"
flake8 ?= "flake8"
setuplib ?= "distutils.core"
epydoc ?= "epydoc"
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
wlevel ?= "once"

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
	rm -rf dist build MANIFEST
	rm -f docs/general.rst
	rm -f docs/changelog.rst
	rm -f docs/makefile.rst
	rm -rf docs/api
	rm -rf docs/html
	rm -rf docs/doctrees
	rm -f  tests/.coverage
	rm -rf tests/htmlcov
	rm -rf tests/cover
	rm -rf tests/examples
	rm -rf tests/pyroute2
	rm -rf pyroute2.egg-info
	rm -f python-pyroute2.spec
	find . -name "*pyc" -exec rm -f "{}" \;
	find . -name "*pyo" -exec rm -f "{}" \;

setup.py docs/conf.py:
	gawk -v version=${version}\
		-v release=${release}\
		-v setuplib=${setuplib}\
		-f configure.gawk $@.in >$@

clean-version:
	rm -f setup.py
	rm -f docs/conf.py

force-version: clean-version update-version

update-version: setup.py docs/conf.py

docs: clean force-version
	cp README.md docs/general.rst
	sed -i '1{s/.*docs\//.. image:: /;s/\ ".*/\n\ \ \ \ :align: right/}' docs/general.rst
	cp README.make.md docs/makefile.rst
	cp CHANGELOG.md docs/changelog.rst
	export PYTHONPATH=`pwd`; make -C docs html; unset PYTHONPATH

epydoc: docs
	${epydoc} -v \
		--no-frames \
		-o docs/api \
		--html \
		--graph all \
		--fail-on-docstring-warning \
		--exclude=pyroute2.netns.process.base_p3 \
		pyroute2/

test: dist
	@export PYTHON=${python}; \
		export NOSE=${nosetests}; \
		export FLAKE8=${flake8}; \
		export WLEVEL=${wlevel}; \
		export SKIP_TESTS=${skip_tests}; \
		export PDB=${pdb}; \
		export COVERAGE=${coverage}; \
		export MODULE=${module}; \
		cd tests; \
		./run.sh general eventlet lnst

upload: clean force-version
	${python} setup.py primary sdist upload

dist: clean force-version docs
	${python} setup.py primary sdist

install: clean force-version
	${python} setup.py primary install ${root} ${lib}

develop: setuplib = "setuptools"
develop: clean force-version
	${python} setup.py primary develop

# 8<--------------------------------------------------------------------
#
# Packages
#
rpm: clean force-version
	cp packages/RedHat/python-pyroute2.spec .
	${python} setup.py primary sdist
	rpmbuild -ta dist/*tar.gz
