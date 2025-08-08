import re
import subprocess


def test_check_modules_fail():
    result = subprocess.run(
        ['make', '-C', '..', 'selftest', 'checkModules=nonsense'],
        capture_output=True,
    )
    error = result.stderr.decode('utf-8').split('\n')
    assert result.returncode == 2
    assert re.match('^To run the tests, python-venv is required$', error[0])
    assert re.match('.+Error 42$', error[1])


def test_check_modules_ok():
    result = subprocess.run(
        ['make', '-C', '..', 'selftest'], capture_output=True
    )
    assert result.returncode == 0
    stdout = result.stdout.decode('utf-8').split('\n')
    assert re.match('^.+Nothing to be done.+selftest.+$', stdout[1])
