clean:
	@rm -f VERSION
	@rm -rf *egg-info
	@rm -rf dist
	@rm -rf build

dist:
	${python} setup.py sdist

install:
	${python} setup.py install ${root} ${lib}

uninstall:
	${python} -m pip uninstall -y pyroute2.ipset

develop:
	${python} setup.py develop
