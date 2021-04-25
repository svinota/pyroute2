#!/usr/bin/env python
import subprocess

version_file = 'pyroute2/config/version.py'


def get_project_version():
    '''
    Get the project version
    '''
    try:
        version = (subprocess
                   .check_output(('git', 'describe'))
                   .decode('utf-8')
                   .strip()
                   .split('-'))
    except subprocess.CalledProcessError:
        version = ['unknown']

    if len(version) > 1:
        version = '{version[0]}.post{version[1]}'.format(**locals())
    else:
        version = version[0]
    return version


def write_version_file(version_file, version):
    '''
    Create and (over)write the version file
    '''
    with open(version_file, 'w') as f:
        f.write('__version__ = "%s"\n' % version)


if __name__ == '__main__':
    write_version_file(version_file, get_project_version())
