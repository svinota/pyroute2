import getpass
import os
import sys

import nox

nox.options.envdir = f'./.nox-{getpass.getuser()}'
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ['linter', 'unit', 'linux-3.6', 'linux-3.10']

linux_kernel_modules = [
    'dummy',
    'bonding',
    '8021q',
    'mpls_router',
    'mpls_iptunnel',
    'l2tp_ip',
    'l2tp_eth',
    'l2tp_netlink',
]


def options(module):
    '''Return pytest options set.'''
    return [
        'python',
        '-m',
        'pytest',
        '--basetemp',
        './log',
        '--cov-report=html',
        '--cov=pyroute2',
        '--exitfirst',
        '--verbose',
        '--junitxml=junit.xml',
        module,
    ]


def setup_linux(session):
    '''Setup a Linux system.

    Load all the modules, but ignore any errors: missing kernel API
    will be handled at the test module level. Same for sysctl.
    '''
    if sys.platform == 'linux' and getpass.getuser() == 'root':
        for module in linux_kernel_modules:
            session.run(
                'modprobe', module, external=True, success_codes=[0, 1]
            )
        session.run(
            'sysctl',
            'net.mpls.platform_labels=2048',
            external=True,
            success_codes=[0, 255],
        )


def setup_venv_common(session, flavour='dev'):
    session.install('--upgrade', 'pip')
    session.install('-r', f'requirements.{flavour}.txt')
    session.install('.')
    return os.path.abspath(session.create_tmp())


def setup_venv_dev(session):
    tmpdir = setup_venv_common(session)
    session.run('cp', '-a', 'tests', tmpdir, external=True)
    session.run('cp', '-a', 'examples', tmpdir, external=True)
    session.chdir(f'{tmpdir}/tests')
    return tmpdir


def setup_venv_docs(session):
    tmpdir = setup_venv_common(session, 'docs')
    session.run('cp', '-a', 'docs', tmpdir)
    [
        session.run('cp', src, dst, external=True)
        for (src, dst) in (
            ('README.rst', f'{tmpdir}/docs/general.rst'),
            ('README.report.md', f'{tmpdir}/docs/report.rst'),
            ('CHANGELOG.md', f'{tmpdir}/docs/changelog.rst'),
        )
    ]
    return tmpdir


@nox.session(name='test-platform')
def test_platform(session):
    '''Test platform capabilities. Requires root to run.'''
    setup_venv_common(session)
    session.run('pyroute2-test-platform')


@nox.session
def docs(session):
    '''Generate project docs.'''
    tmpdir = setup_venv_docs(session)
    cwd = os.path.abspath(os.getcwd())
    session.chdir(f'{tmpdir}/docs/')
    session.run('make', 'html', external=True)
    session.run('cp', '-a', 'html', f'{cwd}/docs/', external=True)
    session.chdir(cwd)
    session.run('util/aafigure_mapper.sh')


@nox.session
def linter(session):
    '''Run code checks and linters.'''
    session.install('pre-commit')
    session.run('pre-commit', 'run', '-a')


@nox.session
def unit(session):
    '''Run unit tests.'''
    setup_venv_dev(session)
    session.run(*options('test_unit'))


@nox.session(python=['3.6', '3.10'])
def linux(session):
    '''Run Linux functional tests. Requires root to run all the tests.'''
    setup_linux(session)
    session.run(
        *options('test_linux'),
        env={'WORKSPACE': setup_venv_dev(session), 'SKIPDB': 'postgres'},
    )


@nox.session(python=['3.10'])
def openbsd(session):
    '''Run OpenBSD tests. Requires OpenBSD >= 7.1'''
    setup_venv_dev(session)
    session.run(*options('test_openbsd'))


@nox.session(python=['3.10'])
def neutron(session):
    '''Run Neutron integration tests.'''
    setup_venv_dev(session)
    session.run(*options('test_neutron'))


@nox.session
def build(session):
    '''Run package build.'''
    session.install('build')
    session.install('twine')
    session.run('python', '-m', 'build')
    session.run('python', '-m', 'twine', 'check', 'dist/*')
