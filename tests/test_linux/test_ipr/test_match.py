from functools import partial


def test_match_callable(context):
    assert len(tuple(context.ipr.get_links(match=partial(lambda x: x)))) > 0
