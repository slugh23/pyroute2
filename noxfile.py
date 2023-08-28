import getpass
import json
import os
import subprocess
import sys

import nox

nox.options.envdir = f'./.nox-{getpass.getuser()}'
nox.options.reuse_existing_virtualenvs = False
nox.options.sessions = [
    'linter',
    'repo',
    'unit',
    'lab',
    'neutron',
    'integration',
    'linux-3.6',
    'linux-3.10',
    'minimal',
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
]


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
        if session.posargs and len(session.posargs[0]) > 0:
            config = json.loads(session.posargs[0])
        else:
            config = {}
        session.debug(f'session config: {config}')
        return func(session, config)

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
        '--basetemp',
        './log',
        '--exitfirst',
        '--verbose',
        '--junitxml=junit.xml',
    ]
    if config.get('fail_on_warnings'):
        ret.insert(1, 'error')
        ret.insert(1, '-W')
    if config.get('pdb'):
        ret.append('--pdb')
    if config.get('coverage'):
        ret.append('--cov-report=html')
        ret.append('--cov=pyroute2')
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
        session.install('build')
        session.install('twine')
        session.install('-r', 'requirements.dev.txt')
        session.install('-r', 'requirements.docs.txt')
        session.run('mv', '-f', 'setup.cfg', '.setup.cfg.orig', external=True)
        session.run(
            'mv', '-f', 'pyroute2/__init__.py', '.init.py.orig', external=True
        )
        session.run('cp', 'setup.minimal.cfg', 'setup.cfg', external=True)
        session.run(
            'cp', 'pyroute2/minimal.py', 'pyroute2/__init__.py', external=True
        )
        session.run('python', '-m', 'build')
        session.run('python', '-m', 'twine', 'check', 'dist/*')
        session.install('.')
        session.run('mv', '-f', '.setup.cfg.orig', 'setup.cfg', external=True)
        session.run(
            'mv', '-f', '.init.py.orig', 'pyroute2/__init__.py', external=True
        )
        session.run('rm', '-rf', 'build', external=True)
    tmpdir = os.path.abspath(session.create_tmp())
    session.run('cp', '-a', 'lab', tmpdir, external=True)
    session.run('cp', '-a', 'tests', tmpdir, external=True)
    session.run('cp', '-a', 'examples', tmpdir, external=True)
    return tmpdir


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
        ['git', 'ls-files', 'requirements*'], stdout=subprocess.PIPE
    )
    files = [x.decode('utf-8') for x in git_ls_files.stdout.split()]
    for fname in files:
        session.run('cp', '-a', fname, tmpdir, external=True)
    session.chdir(tmpdir)
    return tmpdir


def setup_venv_docs(session):
    tmpdir = setup_venv_common(session, 'docs')
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


@nox.session
def docs(session):
    '''Generate project docs.'''
    tmpdir = setup_venv_docs(session)
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


@nox.session
def linter(session):
    '''Run code checks and linters.'''
    session.install('pre-commit')
    session.run('pre-commit', 'run', '-a')


@nox.session
@add_session_config
def unit(session, config):
    '''Run unit tests.'''
    setup_venv_dev(session)
    session.run(*options('test_unit', config))


@nox.session
@add_session_config
def integration(session, config):
    '''Run integration tests (lnst, kuryr, ...).'''
    setup_venv_dev(session)
    session.run(*options('test_integration', config))


@nox.session(python=['3.6', '3.10'])
@add_session_config
def linux(session, config):
    '''Run Linux functional tests. Requires root to run all the tests.'''
    setup_linux(session)
    workspace = setup_venv_dev(session)
    session.run(
        *options('test_linux', config),
        env={
            'WORKSPACE': workspace,
            'SKIPDB': 'postgres',
            'PYTHONPATH': f'{workspace}/tests/mocklib',
        },
    )


@nox.session
@add_session_config
def minimal(session, config):
    '''Run tests on pyroute2.minimal package.'''
    tmpdir = setup_venv_minimal(session, config)
    session.chdir(f'{tmpdir}/tests')
    session.run(*options('test_minimal', config))


@nox.session
@add_session_config
def lab(session, config):
    '''Test lab code blocks.'''
    workspace = setup_venv_minimal(session, config)
    for fname in os.listdir('dist'):
        if fname.startswith('pyroute2.minimal') and fname.endswith('whl'):
            break
    session.run('python', 'util/make_lab_templates.py', fname, external=True)
    session.run('make', '-C', 'lab', 'html', external=True)
    session.run('cp', f'dist/{fname}', 'lab/_build/html/', external=True)
    # make tests
    session.chdir(f'{workspace}/tests')
    session.run(*options('test_lab', config), env={'WORKSPACE': workspace})


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
    session.run(*options('test_neutron', config))


@nox.session
@add_session_config
def repo(session, config):
    '''Run repo tests.'''
    setup_venv_repo(session)
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
