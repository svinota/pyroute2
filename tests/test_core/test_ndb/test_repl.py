import ast
import code
import contextlib
import io
import sys

import pytest


def check_output(source, combined, *func):
    parsed = ast.literal_eval(source)
    assert len(parsed) == len(func)
    return combined(*[f(v) for v, f in zip(parsed, func)])


@pytest.mark.parametrize(
    ('script', 'check', 'combined_record', 'combined_total'),
    (
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                'ndb.interfaces.summary()',
                'ndb.close()',
            ),
            (
                lambda v: v == 'localhost',
                lambda v: v == 0,
                lambda v: isinstance(v, int) and v > 0,
                lambda v: isinstance(v, str) and 0 < len(v) < 16,
                lambda v: isinstance(v, str) or v is None,
                lambda v: isinstance(v, int) and v > 0,
                lambda v: isinstance(v, str) or v is None,
            ),
            lambda *r: all(r),
            lambda *s: all(s),
        ),
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                's = ndb.interfaces.summary()',
                's.select_fields("target", "index")',
                's',
                's',
            ),
            (
                lambda v: v == 'localhost',
                lambda v: isinstance(v, int) and v == 1,
            ),
            lambda *r: all(r),
            lambda *s: sum(s) == 3,
        ),
    ),
    ids=('summary', 'select_fields+repr'),
)
def test_report_pipe(script, check, combined_record, combined_total):
    output = io.StringIO()
    console = code.InteractiveConsole()
    sys.ps1 = ''
    with contextlib.redirect_stdout(output):
        for line in script:
            console.push(line)
    assert combined_total(
        *[
            check_output(source, combined_record, *check)
            for source in output.getvalue().split('\n')
            if len(source) > 0
        ]
    )
