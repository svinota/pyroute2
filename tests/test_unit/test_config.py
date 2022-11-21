from pyroute2 import config


def test_kernel_version():
    versions = {
        '1.2.3-test01': [1, 2, 3],
        '1.2.3.test01': [1, 2, 3],
        '10.1.12': [10, 1, 12],
        'test.10.12': [],
        '2.10.test01': [2, 10],
        '5.16.5-200.fc35.x86_64': [5, 16, 5],
        '5.15.15.debug': [5, 15, 15],
    }

    for key, value in versions.items():
        assert config.parse_kernel_version(key) == value
