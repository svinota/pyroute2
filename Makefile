# 	Copyright (c) 2013 Peter V. Saveliev
#
# 	This file is part of pyroute2 project.
#
# 	PyVFS is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 2 of the License, or
# 	(at your option) any later version.
#
# 	PyVFS is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with PyVFS; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

version ?= "0.2"
release ?= "0.2.10"
python ?= "/usr/bin/python"
nosetests ?= "/usr/bin/nosetests"

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


all:
	@echo targets: dist, install

clean: clean-version
	rm -rf dist build MANIFEST
	rm -f docs/general.rst
	rm -f docs/changelog.rst
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
	cp CHANGELOG.md docs/changelog.rst
	export PYTHONPATH=`pwd`; make -C docs html

test:
	@flake8 --exclude=docs .
	@export PYTHONPATH=`pwd`; cd tests; \
		[ "`id | sed 's/uid=[0-9]\+(\([A-Za-z]\+\)).*/\1/'`" = "root" ] && ulimit -n 2048; \
		${python} -W error ${nosetests} -v ${pdb} \
			--with-coverage \
			--cover-package=pyroute2 \
			${coverage} \
			--cover-erase; \
		cd ..

upload: clean force-version
	${python} setup.py sdist upload

dist: clean force-version
	${python} setup.py sdist

install: clean force-version
	${python} setup.py install ${root} ${lib}

