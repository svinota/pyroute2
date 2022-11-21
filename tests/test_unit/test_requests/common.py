from pyroute2.requests.main import RequestProcessor


class Request(dict):
    pass


class Result(dict):
    pass


def run_test(config, spec, result):
    processor = RequestProcessor(context=spec, prime=spec)
    for fspec in config['filters']:
        processor.apply_filter(fspec['class'](*fspec['argv']))
    processor.finalize()
    assert Result(processor) == result
