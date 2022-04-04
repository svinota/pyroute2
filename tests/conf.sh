#
#

VERSION=`git describe`

[ -z "$LOOP" ] && export LOOP=1
[ -z "$PYTHON" ] && export PYTHON=python
[ -z "$PYTEST" ] && export PYTEST=pytest
[ -z "$WLEVEL" ] || export WLEVEL="-W $WLEVEL"
[ -z "$PDB" ] || export PDB="--pdb --pdb-failures"
[ -z "$COVERAGE" ] || export COVERAGE="--cover-html"
[ -z "$WORKSPACE" ] && export WORKSPACE="$TOP/tests-workspaces/$$"
