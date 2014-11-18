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
release := $(shell git describe)
##
# Python and nosetests versions
#
python ?= "python"
nosetests ?= "nosetests"
##
# Python -W flags:
#
#  ignore  -- completely ignore
#  default -- default action
#  all     -- print all warnings
#  module  -- print the first warning occurence for a module
#  once    -- print each warning only once
#  error   -- fail on any warning (NB: default for our test cycle)
#
#  Would you like to know more? See man 1 python
#
wlevel ?= "error"

##
# Other options
#
# root      -- install root (default: platform default)
# lib       -- lib installation target (default: platform default)
# coverage  -- whether to produce html coverage (default: false)
# pdb       -- whether to run pdb on errors (default: false)
#
ifdef root
	override root := "--root=${root}"
endif

ifdef lib
	override lib := "--install-lib=${lib}"
endif

ifdef coverage
	override coverage := "--cover-html"
endif

ifdef pdb
	override pdb := --pdb --pdb-failures
endif

ifdef wlevel
	override wlevel := -W ${wlevel}
endif


all:
	@echo targets: dist, install

clean: clean-version
	rm -rf dist build MANIFEST
	rm -f docs/general.rst
	rm -f docs/changelog.rst
	rm -f docs/makefile.rst
	rm -rf docs/_build/html
	rm -f  tests/.coverage
	rm -rf tests/htmlcov
	rm -rf tests/cover
	find . -name "*pyc" -exec rm -f "{}" \;

setup.py docs/conf.py:
	gawk -v version=${version} -v release=${release} -v flavor=${flavor}\
		-f configure.gawk $@.in >$@

clean-version:
	rm -f setup.py
	rm -f docs/conf.py

force-version: clean-version update-version

update-version: setup.py docs/conf.py

docs: clean force-version
	cp README.md docs/general.rst
	cp README.make.md docs/makefile.rst
	cp CHANGELOG.md docs/changelog.rst
	export PYTHONPATH=`pwd`; make -C docs html

test:
	@export PYTHONPATH=`pwd`; cd tests; \
		[ -z "$$VIRTUAL_ENV" ] || \
			. $$VIRTUAL_ENV/bin/activate ; \
		[ -z "$$VIRTUAL_ENV" ] || \
			echo "Running in Virtualenv" ; \
		[ "`id | sed 's/uid=[0-9]\+(\([A-Za-z]\+\)).*/\1/'`" = "root" ] && { \
			echo "Running as root" ; \
			ulimit -n 4096 ; \
			modprobe dummy 2>/dev/null ||: ; \
			modprobe bonding 2>/dev/null ||: ; \
			modprobe 8021q 2>/dev/null ||: ; \
		} ; \
		echo "8<----------------------------------" ; \
		echo "python: `which ${python}` [`${python} --version 2>&1`]" ; \
		echo "flake8: `which flake8` [`flake8 --version 2>&1`]" ; \
		echo "nosetests: `which ${nosetests}` [`${nosetests} --version 2>&1`]" ; \
		echo "8<----------------------------------" ; \
		flake8 --exclude=docs .. && echo "flake8 ... ok" || exit 250; \
		[ -z "$$TRAVIS" ] && { \
			${python} ${wlevel} `which ${nosetests}` -v ${pdb} \
			--with-coverage \
			--cover-package=pyroute2 \
			${coverage} \
			--cover-erase || exit 251; \
		} ; \
		cd .. ;

upload: clean force-version
	${python} setup.py sdist upload

dist: clean force-version
	${python} setup.py sdist

install: clean force-version
	${python} setup.py install ${root} ${lib}

testdeps:
	pip install coverage
	pip install flake8
