##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#
python ?= $(shell util/find_python.sh)

.PHONY: all
all:
	@echo targets:
	@echo
	@echo \* clean -- clean all generated files
	@echo \* docs -- generate project docs
	@echo \* dist -- create the package file
	@echo \* test -- run all the tests
	@echo \* install -- install lib into the system or the current virtualenv
	@echo \* uninstall -- uninstall lib
	@echo

.PHONY: clean
clean:
	@$(MAKE) -C lab clean
	@$(MAKE) -C docs clean
	@rm -f lab/*html
	@rm -f lab/_static/conf.js
	@rm -rf dist build MANIFEST
	@rm -f docs-build.log
	@rm -rf pyroute2.egg-info
	@find pyroute2 -name "*pyc" -exec rm -f "{}" \;
	@find pyroute2 -name "*pyo" -exec rm -f "{}" \;
	@git checkout VERSION 2>/dev/null ||:

.PHONY: VERSION
VERSION:
	@${python} util/update_version.py

.PHONY: docs
docs:
	@nox -e docs

.PHONY: format
format:
	@nox -e linter

.PHONY: test
test:
	@nox

.PHONY: test-platform
test-platform:
	@nox -e test_platform

.PHONY: upload
upload: dist
	${python} -m twine upload dist/*

.PHONY: setup
setup:
	$(MAKE) VERSION

.PHONY: dist
dist: setup
	@nox -e build

.PHONY: dist-minimal
dist-minimal:
	mv -f setup.cfg setup.cfg.orig
	cp setup.minimal.cfg setup.cfg
	$(MAKE) dist
	mv -f setup.cfg.orig setup.cfg

.PHONY: install
install:
	$(MAKE) uninstall
	$(MAKE) clean
	$(MAKE) dist
	${python} -m pip install dist/pyroute2-*whl ${root}

.PHONY: install-minimal
install-minimal: dist-minimal
	${python} -m pip install dist/pyroute2.minimal*whl ${root}

.PHONY: uninstall
uninstall:
	${python} -m pip uninstall -y pyroute2
	${python} -m pip uninstall -y pyroute2-minimal

.PHONY: audit-imports
audit-imports:
	findimports -n pyroute2 2>/dev/null | awk -f util/imports_dict.awk

.PHONY: nox
nox:
	${python} -m venv .venv
	bash -c "source .venv/bin/activate; \
		python -m pip install --upgrade pip; \
		python -m pip install nox; \
		nox -e ${session}"
