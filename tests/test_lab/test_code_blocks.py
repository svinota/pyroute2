import os
import pathlib
import sys

import pytest


def get_examples(*argv):
    root = pathlib.Path(os.environ['WORKSPACE'])
    examples = [
        example
        for example in root.joinpath(*argv).iterdir()
        if example.is_dir()
    ]
    return {
        'argnames': 'example',
        'argvalues': examples,
        'ids': [x.name for x in examples],
    }


@pytest.mark.parametrize(**get_examples('examples', 'lab'))
def test_block(example, pytester):
    os.chdir(example.as_posix())
    result = pytester.run(sys.executable, 'check.py')
    assert result.ret == 0
