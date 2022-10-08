##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#
python ?= $(shell util/find_python.sh)

define nox
	[ -d .venv ] || ${python} -m venv .venv
	bash -c "source .venv/bin/activate; \
		python -m pip install --upgrade pip; \
		python -m pip install nox; \
		nox $(1) -- '$(subst ",\",${noxconfig})'"
endef

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

.PHONY: git-clean
git-clean:
	git clean -d -f -x
	git remote prune origin
	git branch --merged >/tmp/merged-branches && \
		vi /tmp/merged-branches && xargs git branch -d </tmp/merged-branches

.PHONY: clean
clean:
	@rm -f lab/*html
	@rm -f lab/_static/conf.js
	@rm -rf lab/_build
	@rm -rf docs/html
	@rm -rf docs/man
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
	$(call nox,-e docs)

.PHONY: lab
lab:
	$(call nox,-e lab)

.PHONY: format
format:
	$(call nox,-e linter)

.PHONY: test
test:
	$(call nox,)

.PHONY: test-platform
test-platform:
	$(call nox,-e test_platform)

.PHONY: upload
upload: dist
	${python} -m twine upload dist/*

.PHONY: setup
setup:
	$(MAKE) VERSION

.PHONY: dist
dist: setup
	$(call nox,-e build)

.PHONY: dist-minimal
dist-minimal: setup
	mv -f setup.cfg setup.cfg.orig
	cp setup.minimal.cfg setup.cfg
	$(call nox,-e build)
	mv -f setup.cfg.orig setup.cfg

.PHONY: install
install: setup
	$(MAKE) uninstall
	$(MAKE) clean
	$(call nox,-e build)
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
	$(call nox,-e ${session})
