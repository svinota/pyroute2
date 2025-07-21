import copy
import getpass
import json
import os
import subprocess
import sys

import nox

nox.options.envdir = f'./.nox-{getpass.getuser()}'
nox.options.reuse_existing_virtualenvs = False
nox.options.sessions = [
    'linter-python3.9',
    'linter-python3.14',
    'ci-self-python3.9',
    'ci-self-python3.14',
    'repo',
    'unit',
    'limits',
    'neutron',
    'process',
    'integration',
    'core-python3.9',
    'core-python3.14',
    'linux-python3.9',
    'linux-python3.14',
    'minimal-python3.9',
    'minimal-python3.14',
]

linux_kernel_modules = [
    'dummy',
    'bonding',
    '8021q',
    'mpls_router',
    'mpls_iptunnel',
    'l2tp_ip',
    'l2tp_eth',
    'l2tp_netlink',
    'netdevsim',
]


def load_global_config():
    if sys.argv[-2] == '--' and len(sys.argv[-1]):
        return json.loads(sys.argv[-1])
    return {}


global_config = load_global_config()
if global_config.get('fast'):
    nox.options.reuse_venv = 'yes'
    nox.options.no_install = True


def add_session_config(func):
    '''Decorator to load the session config.

    Usage::

        @nox.session
        @load_session_config
        def my_session_func(session, config):
            pass

    Command line usage::

        nox -e my_session_name -- '{"option": value}'

    The session config must be a valid JSON dictionary of options.
    '''

    def wrapper(session):
        return func(session, global_config)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__has_user_config__ = True
    return wrapper


def options(module, config):
    '''Return pytest options set.'''
    ret = [
        'python',
        '-m',
        'pytest',
        f'-r{config.get("summary", "x")}',
        f'--timeout={config.get("timeout", 60)}',
        '--basetemp',
        './log',
    ]
    if config.get('exitfirst', True):
        ret.append('--exitfirst')
    if config.get('verbose', True):
        ret.append('--verbose')
    if config.get('coverage', False):
        ret.append('--cov=pyroute2')
        ret.append('--cov-report=html')
    if config.get('profile', False):
        ret.append('--profile')
        ret.append('--profile-svg')
    if config.get('fail_on_warnings'):
        ret.insert(1, 'error')
        ret.insert(1, '-W')
    if config.get('pdb'):
        ret.append('--pdb')
    if config.get('tests_prefix'):
        module = f'{config["tests_prefix"]}/{module}'
    if config.get('sub'):
        module = f'{module}/{config["sub"]}'
    ret.append(module)
    return ret


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


def setup_venv_minimal(session, config):
    if not config.get('reuse'):
        session.install('--upgrade', 'pip')
        session.install('.[dev]')
        session.install('.[docs]')
        session.run(
            'mv', '-f', 'pyproject.toml', '.pyproject.toml.full', external=True
        )
        session.run(
            'mv', '-f', 'pyroute2/__init__.py', '.init.py.full', external=True
        )
        session.run(
            'cp', 'pyproject.minimal.toml', 'pyproject.toml', external=True
        )
        session.run(
            'cp', 'pyroute2/minimal.py', 'pyroute2/__init__.py', external=True
        )
        session.run('python', '-m', 'build')
        session.run('python', '-m', 'twine', 'check', 'dist/*')
        session.install('.')
        session.run(
            'mv', '-f', '.pyproject.toml.full', 'pyproject.toml', external=True
        )
        session.run(
            'mv', '-f', '.init.py.full', 'pyroute2/__init__.py', external=True
        )
        session.run('rm', '-rf', 'build', external=True)
    tmpdir = os.path.abspath(session.create_tmp())
    session.run('cp', '-a', 'tests', tmpdir, external=True)
    session.run('cp', '-a', 'examples', tmpdir, external=True)
    return tmpdir


def setup_venv_common(session, flavour='dev', config=None):
    if config is None:
        config = {}
    if not config.get('fast'):
        session.install('--upgrade', 'pip')
        session.install(f'.[{flavour}]')
        session.install('.')
    return os.path.abspath(session.create_tmp())


def setup_venv_dev(session, config=None):
    if config is None:
        config = {}
    if config.get('fast'):
        return os.getcwd()
    tmpdir = setup_venv_common(session)
    session.run('cp', '-a', 'tests', tmpdir, external=True)
    session.run('cp', '-a', 'examples', tmpdir, external=True)
    session.chdir(f'{tmpdir}/tests')
    return tmpdir


def setup_venv_repo(session):
    tmpdir = setup_venv_common(session, 'repo')
    for item in (
        ('tests', tmpdir),
        ('noxfile.py', tmpdir),
        ('VERSION', tmpdir),
        ('CHANGELOG.rst', tmpdir),
    ):
        session.run('cp', '-a', *item, external=True)
    git_ls_files = subprocess.run(
        ['git', 'ls-files', 'pyproject*'], stdout=subprocess.PIPE
    )
    files = [x.decode('utf-8') for x in git_ls_files.stdout.split()]
    for fname in files:
        session.run('cp', '-a', fname, tmpdir, external=True)
    session.chdir(tmpdir)
    return tmpdir


def setup_venv_docs(session, config=None):
    tmpdir = setup_venv_common(session, flavour='docs', config=config)
    session.run('cp', '-a', 'docs', tmpdir, external=True)
    session.run('cp', '-a', 'examples', tmpdir, external=True)
    [
        session.run('cp', src, dst, external=True)
        for (src, dst) in (
            ('README.rst', f'{tmpdir}/docs/general.rst'),
            ('README.report.rst', f'{tmpdir}/docs/report.rst'),
            ('README.contribute.rst', f'{tmpdir}/docs/devcontribute.rst'),
            ('CHANGELOG.rst', f'{tmpdir}/docs/changelog.rst'),
        )
    ]
    return tmpdir


@nox.session(name='test-platform')
def test_platform(session):
    '''Test platform capabilities. Requires root to run.'''
    setup_venv_common(session)
    session.run('pyroute2-test-platform')


@nox.session(python='python3.10')
@add_session_config
def docs(session, config):
    '''Generate project docs.'''
    tmpdir = setup_venv_docs(session, config)
    cwd = os.path.abspath(os.getcwd())
    # man pages
    session.chdir(f'{tmpdir}/docs/')
    session.run('make', 'man', 'SPHINXOPTS="-W"', external=True)
    session.run('cp', '-a', 'man', f'{cwd}/docs/', external=True)
    # html
    session.chdir(f'{tmpdir}/docs/')
    session.run('make', 'html', 'SPHINXOPTS="-W"', external=True)
    session.run('cp', '-a', 'html', f'{cwd}/docs/', external=True)
    session.run('make', 'doctest', external=True)
    session.chdir(cwd)
    session.run('bash', 'util/aafigure_mapper.sh', external=True)
    #
    session.log('8<---------------------------------------------------------')
    session.log('compiled docs:')
    session.log(f'html pages -> {cwd}/docs/html')
    session.log(f'man pages -> {cwd}/docs/man')


@nox.session(
    python=[
        'python3.9',
        'python3.10',
        'python3.11',
        'python3.12',
        'python3.13',
        'python3.14',
    ]
)
@add_session_config
def linter(session, config):
    '''Run code checks and linters.'''
    if not config.get('fast'):
        session.install('pre-commit')
        session.install('mypy')
    session.run('pre-commit', 'run', '-a')
    with open('.mypy-check-paths', 'r') as f:
        session.run(
            'python',
            '-m',
            'mypy',
            *f.read().split(),
            env={'PYTHONPATH': os.getcwd()},
        )


@nox.session
@add_session_config
def unit(session, config):
    '''Run unit tests.'''
    setup_venv_dev(session)
    session.run(*options('test_unit', config))


@nox.session
@add_session_config
def decoder(session, config):
    '''Run decoder tests.'''
    setup_venv_dev(session)
    session.run(*options('test_decoder', config))


@nox.session
@add_session_config
def integration(session, config):
    '''Run integration tests (lnst, kuryr, ...).'''
    setup_venv_dev(session)
    session.run(*options('test_integration', config))


def test_common(session, config, module):
    setup_linux(session)
    workspace = setup_venv_dev(session, config)
    path = f'{workspace}/tests/mocklib'
    if config.get('fast'):
        path += f':{workspace}'
        session.chdir('tests')
    session.run(
        *options(module, config),
        env={'WORKSPACE': workspace, 'SKIPDB': 'postgres', 'PYTHONPATH': path},
    )


@nox.session(
    name='ci-self',
    python=[
        'python3.9',
        'python3.10',
        'python3.11',
        'python3.12',
        'python3.13',
        'python3.14',
    ],
)
@add_session_config
def ci(session, config):
    '''Run ci self-test. No root required.'''
    test_common(session, config, 'test_ci')


@nox.session(
    python=[
        'python3.9',
        'python3.10',
        'python3.11',
        'python3.12',
        'python3.13',
        'python3.14',
    ]
)
@add_session_config
def linux(session, config):
    '''Run Linux functional tests. Requires root to run all the tests.'''
    test_common(session, config, 'test_linux')


@nox.session(
    python=[
        'python3.9',
        'python3.10',
        'python3.11',
        'python3.12',
        'python3.13',
        'python3.14',
    ]
)
@add_session_config
def core(session, config):
    '''Run Linux tests in asyncio.'''
    test_common(session, config, 'test_core')


@nox.session
@add_session_config
def limits(session, config):
    '''Run limits & stress testing.'''
    test_common(session, config, 'test_limits')


@nox.session
@add_session_config
def process(session, config):
    '''Test child process module.'''
    setup_venv_dev(session)
    session.run(*options('test_process', config))


@nox.session(
    python=[
        'python3.9',
        'python3.10',
        'python3.11',
        'python3.12',
        'python3.13',
        'python3.14',
    ]
)
@add_session_config
def minimal(session, config):
    '''Run tests on pyroute2.minimal package.'''
    tmpdir = setup_venv_minimal(session, config)
    session.chdir(f'{tmpdir}/tests')
    session.run(*options('test_minimal', config))


@nox.session
@add_session_config
def openbsd(session, config):
    '''Run OpenBSD tests. Requires OpenBSD >= 7.1'''
    setup_venv_dev(session)
    session.run(*options('test_openbsd', config))


@nox.session
@add_session_config
def windows(session, config):
    '''Rin Windows tests.'''
    setup_venv_dev(session)
    session.run(*options('test_windows', config))


@nox.session
@add_session_config
def neutron(session, config):
    '''Run Neutron integration tests.'''
    setup_venv_dev(session)
    session.install('eventlet')
    session.run(*options('test_neutron', config))


@nox.session
@add_session_config
def repo(session, config):
    '''Run repo tests.'''
    setup_venv_repo(session)
    config = copy.copy(config)
    config['tests_prefix'] = 'tests'
    session.run(*options('test_repo', config))


@nox.session
def build(session):
    '''Run package build.'''
    session.install('build')
    session.install('twine')
    session.run('python', '-m', 'build')
    session.run('python', '-m', 'twine', 'check', 'dist/*')


@nox.session
@add_session_config
def build_minimal(session, config):
    '''Build the minimal package'''
    setup_venv_minimal(session, config)


@nox.session
@add_session_config
def upload(session, config):
    '''Upload built packages'''
    session.install('twine')
    session.run('python', '-m', 'twine', 'upload', 'dist/*')
