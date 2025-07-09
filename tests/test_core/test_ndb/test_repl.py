import ast
import code
import contextlib
import io
import sys

import pytest


def check_output(source, combined, *func):
    parsed = ast.literal_eval(source)
    if len(parsed) != len(func):
        return False
    return combined(*[f(v) for v, f in zip(parsed, func)])


@pytest.mark.parametrize(
    ('script', 'check', 'combined_fields', 'combined_records'),
    (
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                '# output repr() of a summary',
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
                '# no repr() expected',
                's = ndb.interfaces.summary()',
                '# select_fields() returns report -> repr()',
                's.select_fields("target", "index")'
                '# one more repr(), must NOT be empty',
                's',
                '# one more repr(), must NOT be empty',
                's',
                'ndb.close()',
            ),
            (
                lambda v: v == 'localhost',
                lambda v: isinstance(v, int) and v == 1,
            ),
            lambda *r: all(r),
            lambda *s: sum(s) == 3,
        ),
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                's = ndb.interfaces.summary()',
                '_ = s.select_fields("index", "ifname")',
                '_ = s.select_records(**{"ifname": lambda v: v == "lo"})',
                's',
                's',
                'ndb.close()',
            ),
            (lambda v: v == 1, lambda v: v == 'lo'),
            lambda *r: all(r),
            lambda *s: sum(s) == 2,
        ),
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                's = ndb.addresses.summary()',
                '(s',
                '   .transform_fields(',
                '       address=lambda r: f"{r.address}/{r.prefixlen}"',
                '   )' '   .select_fields(',
                '       "ifname", "address",' '   )',
                ')',
                'ndb.close()',
            ),
            (lambda v: v == 'lo', lambda v: v == '127.0.0.1/8'),
            lambda *r: all(r),
            lambda *s: sum(s) == 1,
        ),
        (
            (
                'from pyroute2 import NDB, netns',
                'from pyroute2.common import uifname',
                'nsname = uifname()',
                'ndb = NDB(',
                '   sources=[',
                '       {',
                '           "target": "localhost",',
                '           "netns": nsname,',
                '       }',
                '   ],',
                ')',
                'ndb.interfaces["lo"].set("state", "up").commit()',
                '(ndb ',
                '   .addresses',
                '   .summary()',
                '   .select_records(address="127.0.0.1")',
                '   .count(),',
                ')',
                'ndb.close()',
                'netns.remove(nsname)',
            ),
            (lambda v: v == 1,),
            lambda *r: sum(r) == 1,
            lambda *s: sum(s) == 1,
        ),
        (
            (
                'import json',
                'from pyroute2 import NDB',
                'ndb = NDB()',
                'report = "".join(',
                '    ndb',
                '        .routes',
                '        .summary()',
                '        .select_fields("dst", "ifname")',
                '        .format("json")',
                ')',
                '(',
                '    len(',
                '        tuple(',
                '            filter(',
                '                lambda x: x["dst"] == "127.0.0.1",',
                '                json.loads(report)',
                '            )',
                '        )',
                '    ),',
                ')',
                'ndb.close()',
            ),
            (lambda v: v == 1,),
            lambda *r: sum(r) == 1,
            lambda *s: sum(s) == 1,
        ),
        (
            (
                'from pyroute2 import NDB',
                'ndb = NDB()',
                's = ndb.routes.summary().format("csv")',
                's',
                's',
                'ndb.close()',
            ),
            (
                lambda v: v == 'target',
                lambda v: v == 'tflags',
                lambda v: v == 'table',
                lambda v: v == 'ifname',
                lambda v: v == 'dst',
                lambda v: v == 'dst_len',
                lambda v: v == 'gateway',
            ),
            lambda *r: all(r),
            lambda *s: sum(s) == 2,
        ),
    ),
    ids=(
        'summary',
        'select_fields+repr x2',
        'select_records+repr x2',
        'transform_fields+repr',
        'count',
        'format(json)',
        'format(csv)',
    ),
)
def test_report(script, check, combined_fields, combined_records):
    output = io.StringIO()
    console = code.InteractiveConsole()
    sys.ps1 = ''
    with contextlib.redirect_stdout(output):
        for line in script:
            console.push(line)
    assert combined_records(
        *[
            check_output(source, combined_fields, *check)
            for source in output.getvalue().split('\n')
            if len(source) > 0
        ]
    )
