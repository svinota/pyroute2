
#
# configuration script for run.sh
#

MODULES="general eventlet integration unit"

[ -z "$LOOP" ] && export LOOP=1
[ -z "$REPORT" ] && export REPORT="http://localhost:8080/"
[ -z "$PYTHON" ] && export PYTHON=python
[ -z "$NOSE" ] && export NOSE=nosetests
[ -z "$FLAKE8" ] && export FLAKE8=flake8
[ -z "$WLEVEL" ] || export WLEVEL="-W $WLEVEL"
[ -z "$PDB" ] || export PDB="--pdb --pdb-failures"
[ -z "$COVERAGE" ] || export COVERAGE="--cover-html"
[ -z "$SKIP_TESTS" ] || export SKIP_TESTS="--exclude $SKIP_TESTS"
[ -z "$MODULE" ] || export MODULE=`echo $MODULE | sed -n '/:/{p;q};s/$/:/p'`
