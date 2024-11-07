##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#
python ?= $(shell util/find_python.sh)
platform := $(shell uname -s)

define nox
        {\
		which nox 2>/dev/null || {\
			python -m venv ~/.venv-boot/;\
			. ~/.venv-boot/bin/activate;\
			pip install --upgrade pip;\
			pip install nox;\
		};\
		nox $(1) -- '${noxconfig}';\
	}
endef

all:
	@echo targets:
	@echo
	@echo \* clean -- clean all generated files
	@echo \* docs -- generate project docs \(requires sphinx\)
	@echo \* test -- run functional tests \(see README.make.md\)
	@echo \* install -- install lib into the system
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
		make -C docs html || export FAIL=true ; \
		[ -f docs/_templates/layout.html.orig ] && ( \
			mv -f docs/_templates/layout.html.orig docs/_templates/layout.html; ) ||: ;\
		unset PYTHONPATH ;\
		[ -z "$$FAIL" ] || false

docs: install docs/html

check_parameters:
	@if [ ! -z "${skip_tests}" ]; then \
		echo "'skip_tests' is deprecated, use 'skip=...' instead"; false; fi

.PHONY: test
test:
ifeq ($(platform), Linux)
	$(call nox,)
else ifeq ($(platform), OpenBSD)
	$(call nox,-e openbsd)
else
	$(info >> Platform not supported)
endif

test-platform:
	@${python} -c "\
import logging;\
logging.basicConfig();\
from pr2modules.config.test_platform import TestCapsRtnl;\
from pprint import pprint;\
pprint(TestCapsRtnl().collect())"

upload: dist
	$(call nox,-e upload)

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

dist:
	cd pyroute2; ${python} setup.py sdist
	mkdir dist
	$(call make_modules, dist)
	$(call fetch_modules_dist)

install:
	rm -f dist/pyroute2.minimal*
	${python} -m pip install --no-deps --no-index dist/* ${prefix}

install-minimal: dist
	${python} -m pip install --no-deps --no-index dist/pyroute2.minimal* dist/pyroute2.core* ${prefix}

uninstall: clean VERSION setup
	$(call make_modules, uninstall)

audit-imports:
	for module in $(call list_modules); do \
		echo $$module; \
		findimports -n $$module/pr2modules/ 2>/dev/null | awk -f util/imports_dict.awk | awk '{printf("\t"$$0"\n")}'; \
	done

# deprecated:
epydoc clean-version update-version force-version README.md setup.ini develop:
	@echo Deprecated target, see README.make.md
