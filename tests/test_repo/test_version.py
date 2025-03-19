import io
import re

import pytest
from packaging.version import InvalidVersion, Version


@pytest.fixture
def files():
    context = {}
    for file in ('VERSION', 'CHANGELOG.rst'):
        with open(file, 'r') as f:
            obj = io.StringIO()
            obj.write(f.read())
            obj.seek(0)
            context[file] = obj
    yield context


def test_static_version_file(files):
    assert re.match(
        r'^[0-9]\.[0-9]\.[0-9]{1,2}(a[0-9]+|b[0-9]+|rc[0-9]+){0,1}$',
        files['VERSION'].getvalue().strip(),
    )


def test_changelog(files):
    line = ''
    for line in files['CHANGELOG.rst'].readlines():
        if line[0] == '*':
            break

    try:
        static_version = Version(files['VERSION'].getvalue().strip())
        last_changelog_version = Version(line.split()[1])
    except InvalidVersion as e:
        pytest.fail(f"Invalid version encountered: {e}")

    assert static_version >= last_changelog_version
