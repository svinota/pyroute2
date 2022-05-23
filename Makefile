##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#

make ?= make
##
# Python-related configuration
#
python ?= python
nosetests ?= nosetests
flake8 ?= flake8
black ?= black
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

##
# Functions
#
define list_modules
	`ls -1 | sed -n '/egg-info/n; /pyroute2/p'`
endef

define make_modules
	for module in $(call list_modules); do ${make} -C $$module $(1) python=${python}; done
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
				${python} \
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

.PHONY: all
all:
	@echo targets:
	@echo
	@echo \* clean -- clean all generated files
	@echo \* docs -- generate project docs \(requires sphinx\)
	@echo \* test -- run functional tests \(see README.make.md\)
	@echo \* install -- install lib into the system
	@echo

.PHONY: clean
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
	@rm -f pyroute2/config.json
	@rm -f pyroute2/setup.cfg
	@rm -f pyroute2.minimal/config.json
	@rm -f pyroute2.minimal/setup.cfg
	@find pyroute2 -name "*pyc" -exec rm -f "{}" \;
	@find pyroute2 -name "*pyo" -exec rm -f "{}" \;

VERSION:
	@${python} util/update_version.py
	@for package in $(call list_modules); do cp VERSION $$package; done
	@for package in pyroute2 pyroute2.minimal; do \
		echo '{"version": "'`cat $$package/VERSION`'"}' >$$package/config.json; \
	done

docs/html:
	@cp README.rst docs/general.rst
	@cp README.make.md docs/makefile.rst
	@cp README.report.md docs/report.rst
	@cp CHANGELOG.md docs/changelog.rst
	@[ -f docs/_templates/private.layout.html ] && ( \
	    mv -f docs/_templates/layout.html docs/_templates/layout.html.orig; \
		cp docs/_templates/private.layout.html docs/_templates/layout.html; ) ||:
	@export PYTHONPATH=`pwd`; \
		${make} -C docs html || export FAIL=true ; \
		[ -f docs/_templates/layout.html.orig ] && ( \
			mv -f docs/_templates/layout.html.orig docs/_templates/layout.html; ) ||: ;\
		unset PYTHONPATH ;\
		[ -z "$$FAIL" ] || false
	@find docs -name 'aafig-*svg' -exec ${python} util/aafigure_mapper.py docs/aafigure.map '{}' \;

docs: install docs/html

check_parameters:
	@if [ ! -z "${skip_tests}" ]; then \
		echo "'skip_tests' is deprecated, use 'skip=...' instead"; false; fi

.PHONY: format
format:
	@pre-commit run -a

.PHONY: test
test: check_parameters
	@export PYTHON=${python}; \
		export PYTEST=${pytest}; \
		export WLEVEL=${wlevel}; \
		export PDB=${pdb}; \
		export COVERAGE=${coverage}; \
		export LOOP=${loop}; \
		export WORKSPACE=${workspace}; \
		export PYROUTE2_TEST_DBNAME=${dbname}; \
		export SKIPDB=${skipdb}; \
		export BREAK_ON_ERRORS=${break}; \
		./tests/run_pytest.sh

.PHONY: test-platform
test-platform:
	@cd pyroute2.core; ${python} -c "\
import logging;\
logging.basicConfig();\
from pr2modules.config.test_platform import TestCapsRtnl;\
from pprint import pprint;\
pprint(TestCapsRtnl().collect())"

.PHONY: upload
upload: dist
	${python} -m twine upload dist/*

.PHONY: setup
setup:
	$(call process_templates)
	@for module in $(call list_modules); do $(call deploy_license); done
	@for module in pyroute2 pyroute2.minimal; do \
		${python} \
		    util/process_template.py \
			$$module/setup.cfg.in \
			$$module/config.json \
			$$module/setup.cfg ; \
	done

.PHONY: dist
dist: clean VERSION setup
	cd pyroute2; ${python} setup.py sdist
	mkdir dist
	$(call make_modules, dist)
	$(call fetch_modules_dist)
	${python} -m twine check dist/*

.PHONY: install
install: dist
	rm -f dist/pyroute2.minimal*
	${python} -m pip install dist/* ${root}

.PHONY: install-minimal
install-minimal: dist
	${python} -m pip install dist/pyroute2.minimal* dist/pyroute2.core* ${root}

.PHONY: uninstall
uninstall: clean VERSION setup
	$(call make_modules, uninstall)

.PHONY: audit-imports
audit-imports:
	for module in $(call list_modules); do \
		echo $$module; \
		findimports -n $$module/pr2modules/ 2>/dev/null | awk -f util/imports_dict.awk | awk '{printf("\t"$$0"\n")}'; \
	done

.PHONY: stubs
stubs:
	for module in $(call list_modules); do \
		[ -d $$module/pr2modules/ ] && { echo "--> $$module"; stubgen -o stubs $$module/pr2modules/; } ; \
	done

# deprecated:
epydoc clean-version update-version force-version README.md setup.ini develop pytest test-format:
	@echo Deprecated target, see README.make.md
