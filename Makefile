##
#
#   The pyroute2 project is dual licensed, see README.license.md for details
#
#
ifneq ($(strip $(python)),)
	forcePython := --force-python ${python}
else
	forcePython :=
endif
checkModules ?= ensurepip
python ?= $(shell util/find_python.sh ${checkModules} )
platform := $(shell uname -s)
releaseTag ?= $(shell git describe --tags --abbrev=0 2>/dev/null )
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
		nox ${forcePython} $(1) -- '${noxconfig}';\
	}
endef

.PHONY: selftest
selftest:
ifeq ($(strip $(python)),)
	@echo No suitable python versions found. checkModules: ${checkModules}
	@exit 42
endif

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
	$(call nox,-e linter-$(shell basename ${python}))

.PHONY: test nox
test nox: selftest
ifeq ($(platform), Linux)
	$(call nox,-e ${session})
else ifeq ($(platform), OpenBSD)
	$(call nox,-e openbsd)
else
	$(info >> Platform not supported)
endif

.PHONY: upload
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
setup: selftest
	$(MAKE) VERSION

.PHONY: dist
dist: setup
	$(call nox,-e build)

.PHONY: dist-minimal
dist-minimal: setup
	$(call nox,-e build_minimal)

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
