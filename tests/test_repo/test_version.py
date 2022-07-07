import io
import re

import pytest
from setuptools._vendor import packaging


@pytest.fixture
def files():
    context = {}
    for file in ('VERSION', 'CHANGELOG.md'):
        with open(file, 'r') as f:
            obj = io.StringIO()
            obj.write(f.read())
            obj.seek(0)
            context[file] = obj
    yield context


def test_static_version_file(files):
    assert re.match(
        r'[0-9]\.[0-9]\.[0-9]{1,2}\.post1', files['VERSION'].getvalue().strip()
    )


def test_changelog(files):
    line = ''
    for line in files['CHANGELOG.md'].readlines():
        if line[0] == '*':
            break
    static_version = packaging.version.parse(files['VERSION'].getvalue())
    last_changelog_version = packaging.version.parse(line.split()[1])
    assert static_version >= last_changelog_version
