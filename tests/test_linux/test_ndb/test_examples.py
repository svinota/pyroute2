import os
import pathlib
import sys

import pytest
from pr2test.marks import require_root

pytestmark = [require_root()]


def get_examples(*argv):
    root = pathlib.Path(os.environ['WORKSPACE'])
    examples = [
        file
        for file in root.joinpath(*argv).iterdir()
        if not file.name.endswith('.swp')
    ]
    return {
        'argnames': 'example',
        'argvalues': examples,
        'ids': [x.name for x in examples],
    }


@pytest.mark.parametrize(**get_examples('examples', 'ndb'))
def test_ndb_examples(example, pytester, context):
    argv = []
    with example.open('r') as text:
        for line in text.readlines():
            line = line.strip()
            if line == ':notest:':
                pytest.skip()
            elif line.startswith(':test:argv:'):
                argv.append(line.split(':')[-1])
            elif line.startswith(':test:environ:'):
                key, value = line.split(':')[-1].split('=')
                os.environ[key] = value
    result = pytester.run(sys.executable, example.as_posix(), *argv)
    assert result.ret == 0
