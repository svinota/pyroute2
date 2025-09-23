##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#
python ?= $(shell util/find_python.sh)
platform := $(shell uname -s)
releaseTag ?= $(shell git describe --tags --abbrev=0)
releaseDescription := $(shell git tag -l -n1 ${releaseTag} | sed 's/[0-9. ]\+//')
noxboot ?= ~/.venv-boot

define nox
        {\
		which nox 2>/dev/null || {\
		    test -d ${noxboot} && \
				{\
					. ${noxboot}/bin/activate;\
				} || {\
					${python} -m venv ${noxboot};\
					. ${noxboot}/bin/activate;\
					pip install --upgrade pip;\
					pip install nox;\
				};\
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

.PHONY: git-clean
git-clean:
	git clean -d -f -x
	git remote prune origin
	git branch --merged | grep -vE '(^\*| master )' >/tmp/merged-branches && \
		( xargs git branch -d </tmp/merged-branches ) ||:

.PHONY: clean
clean:
	@for i in `ip -o link | awk -F : '($$2 ~ /^ pr/) {print($$2)}'`; do sudo ip link del $$i; done
	@rm -rf docs/html
	@rm -rf docs/man
	@rm -f tests/*.db
	@rm -f tests/*.json
	@rm -rf dist build MANIFEST
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

.PHONY: format
format:
	$(call nox,-e linter-$(shell basename ${python}))

.PHONY: test nox
test nox:
ifeq ($(platform), Linux)
	$(call nox,-e ${session})
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

.PHONY: release
release: dist
	gh release create \
		--verify-tag \
		--title "${releaseDescription}" \
		${releaseTag} \
		./dist/*${releaseTag}*

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
	findimports -n pyroute2 2>/dev/null | awk -f util/imports_dict.awk
