##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#

##
# Python-related configuration
#
python ?= python
nosetests ?= nosetests
flake8 ?= flake8
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

define list_modules
	`ls -1 | sed -n '/egg-info/n; /pyroute2/p'`
endef

define make_modules
	for module in $(call list_modules); do make -C $$module $(1) python=${python}; done
endef

define fetch_modules_dist
	for module in $(call list_modules); do cp $$module/dist/* dist; done
endef

define clean_module
	if [ -f $$module/setup.json ]; then \
		for i in `ls -1 templates`; do rm -f $$module/$$i; done; \
	fi; \
	rm -f $$module/LICENSE.*; \
	rm -f $$module/README.license.md; \
	rm -f $$module/CHANGELOG.md; \
	rm -f $$module/VERSION; \
	rm -rf $$module/build; \
	rm -rf $$module/dist; \
	rm -rf $$module/*egg-info
endef

define process_templates
	for module in $(call list_modules); do \
		if [ -f $$module/setup.json ]; then \
			for template in `ls -1 templates`; do \
				python \
					util/process_template.py \
					templates/$$template \
					$$module/setup.json \
					$$module/$$template; \
			done; \
		fi; \
	done
endef

define deploy_license
	cp LICENSE.* $$module/ ; \
	cp README.license.md $$module/ ; \
	cp CHANGELOG.md $$module/
endef

all:
	@echo targets:
	@echo
	@echo \* clean -- clean all generated files
	@echo \* docs -- generate project docs \(requires sphinx\)
	@echo \* test -- run functional tests \(see README.make.md\)
	@echo \* install -- install lib into the system
	@echo \* develop -- run \"setup.py develop\" \(requires setuptools\)
	@echo

clean:
	@for module in $(call list_modules); do $(call clean_module); done
	@rm -f VERSION
	@rm -rf dist build MANIFEST
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

VERSION:
	@${python} util/update_version.py
	@for package in $(call list_modules); do cp VERSION $$package; done

docs/html: pyroute2/config/version.py
	@cp README.rst docs/general.rst
	@cp README.make.md docs/makefile.rst
	@cp README.report.md docs/report.rst
	@cp CHANGELOG.md docs/changelog.rst
	@[ -f docs/_templates/private.layout.html ] && ( \
	    mv -f docs/_templates/layout.html docs/_templates/layout.html.orig; \
		cp docs/_templates/private.layout.html docs/_templates/layout.html; ) ||:
	@export PYTHONPATH=`pwd`; \
		make -C docs html || export FAIL=true ; \
		[ -f docs/_templates/layout.html.orig ] && ( \
			mv -f docs/_templates/layout.html.orig docs/_templates/layout.html; ) ||: ;\
		unset PYTHONPATH ;\
		[ -z "$$FAIL" ] || false

docs: docs/html

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
		export SKIPDB=${skipdb}; \
		./tests/run_pytest.sh

test-platform:
	@${python} -c "\
import logging;\
logging.basicConfig();\
from pyroute2.config.test_platform import TestCapsRtnl;\
from pprint import pprint;\
pprint(TestCapsRtnl().collect())"

upload: dist
	${python} -m twine upload dist/*

setup:
	$(call process_templates)
	@for module in $(call list_modules); do $(call deploy_license); done

dist: clean VERSION setup
	pushd pyroute2; ${python} setup.py sdist; popd
	mkdir dist
	$(call make_modules, dist)
	$(call fetch_modules_dist)
	${python} -m twine check dist/*

install: dist
	${python} -m pip install dist/*

uninstall: clean setup
	$(call make_modules, uninstall)

develop: clean VERSION
	$(call make_modules, develop)
	${python} setup.py develop

# deprecated:
epydoc clean-version update-version force-version README.md setup.ini:
	@echo Deprecated target, see README.make.md
