"""Failure-path control tests; fake commands never assert actual host acceptance."""

import contextlib
import importlib.util
import json
import os
import shlex
from pathlib import Path
import sys

import pytest

spec = importlib.util.spec_from_file_location('runtime_release', Path(__file__).resolve().parents[1] / 'runtime_release.py')
release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release
spec.loader.exec_module(release)

CURRENT = 'c' * 40
PREVIOUS = 'a' * 40


class Controlled(release.Release):
    def __init__(self, path, *, fault=None, legacy=False):
        super().__init__(CURRENT, base=path)
        self.events, self.fault, self.legacy = [], fault, legacy

    def step(self, name, *values):
        self.events.append((name, *values))
        if self.fault == name:
            raise release.ReleaseError('Synthetic failure')

    def previous(self):
        self.step('previous')
        return PREVIOUS, self.legacy

    def exact_main(self):
        self.step('exact-main')
        if self.fault == 'main-advanced' and sum(e[0] == 'exact-main' for e in self.events) == 2:
            raise release.ReleaseError('Main advanced')

    def extract(self, destination):
        self.step('extract')

    def build(self, context):
        self.step('build')

    def compose(self, revision, *args, legacy=False):
        name = 'stop' if args[0] == 'stop' else 'data-up' if args[-1] == 'redis' else 'application-up'
        self.step(name, revision, args, legacy)

    def backup(self):
        self.step('backup')
        return 'private.pgdump'

    def migrate(self, revision):
        self.step('migration' if revision == CURRENT else 'rollback-revalidation', revision)

    def ready(self, revision):
        self.step('ready' if revision == CURRENT else 'rollback-ready', revision)


@pytest.fixture
def operation(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def unlocked(path):
        yield
    monkeypatch.setattr(release, 'locked', unlocked)
    return tmp_path


def test_success_orders_backup_before_migration_and_marks_only_after_ready(operation):
    item = Controlled(operation)
    item.deploy()
    names = [e[0] for e in item.events]
    assert names == ['previous', 'exact-main', 'extract', 'build', 'exact-main', 'data-up',
                     'stop', 'backup', 'migration', 'application-up', 'ready']
    assert json.loads((operation / 'runtime-success.json').read_text()) == {
        'revision': CURRENT, 'schema': release.SCHEMA, 'backup': 'private.pgdump'}
    assert (operation / 'runtime-success.json').stat().st_mode & 0o077 == 0
    assert not list(operation.glob('context-*'))


@pytest.mark.parametrize('fault', ['previous', 'exact-main', 'extract', 'build', 'main-advanced', 'data-up'])
def test_pretransition_failure_does_not_stop_or_migrate_existing_application(operation, fault):
    item = Controlled(operation, fault=fault)
    with pytest.raises(release.ReleaseError):
        item.deploy()
    assert not any(e[0] in {'stop', 'backup', 'migration', 'rollback-revalidation'} for e in item.events)
    assert not (operation / 'runtime-success.json').exists()
    assert not list(operation.glob('context-*'))


@pytest.mark.parametrize('fault', ['backup', 'migration', 'ready'])
@pytest.mark.parametrize('legacy', [False, True])
def test_failed_transition_restores_previous_without_downgrade_or_volume_removal(operation, fault, legacy):
    item = Controlled(operation, fault=fault, legacy=legacy)
    with pytest.raises(release.ReleaseError, match='previous service restored'):
        item.deploy()
    assert not (operation / 'runtime-success.json').exists()
    assert ('application-up', PREVIOUS, ('up', '-d', '--wait', '--wait-timeout', '90', 'api')
            if legacy else ('up', '-d', '--wait', '--wait-timeout', '90', 'api', 'worker'), legacy) in item.events
    if legacy:
        assert not any(e[0] in {'rollback-revalidation', 'rollback-ready'} for e in item.events)
    else:
        names = [e[0] for e in item.events]
        assert names.index('rollback-revalidation') < names.index('rollback-ready')
    assert not any('down' in str(e) or 'pg_restore' in str(e) for e in item.events)


def test_failed_schema_security_revalidation_keeps_old_runtime_stopped(operation):
    item = Controlled(operation, fault='ready')
    def deny(revision):
        item.events.append(('denied-rollback-revalidation', revision))
        raise release.ReleaseError('Unsafe actual schema ACL')
    original = item.migrate
    item.migrate = lambda revision: original(revision) if revision == CURRENT else deny(revision)
    with pytest.raises(release.ReleaseError, match='Rollback failed'):
        item.deploy()
    assert not any(e[0] == 'application-up' and e[1] == PREVIOUS for e in item.events)
    assert not (operation / 'runtime-success.json').exists()


def test_success_evidence_write_failure_requires_rollback(operation, monkeypatch):
    def failed_write(*args):
        raise OSError('Synthetic full disk')
    monkeypatch.setattr(release, 'atomic_json', failed_write)
    item = Controlled(operation)
    with pytest.raises(release.ReleaseError, match='previous service restored'):
        item.deploy()
    assert ('rollback-ready', PREVIOUS) in item.events
    assert not (operation / 'runtime-success.json').exists()


@pytest.mark.parametrize('data', [None, {}, {'status': 'ready', 'revision': PREVIOUS},
    {'status': 'ready', 'revision': CURRENT, 'checks': {'process': 'up', 'database': 'up', 'queue': 'up', 'worker': 'down'}}])
def test_health_or_stale_worker_is_not_runtime_readiness(tmp_path, data):
    item = release.Release(CURRENT, base=tmp_path, read_ready=lambda: data)
    with pytest.raises(release.ReleaseError):
        item.ready(CURRENT)


def test_exact_readiness_checks_every_dependency_and_revision(tmp_path):
    item = release.Release(CURRENT, base=tmp_path, read_ready=lambda: {
        'status': 'ready', 'revision': CURRENT, 'checks': dict.fromkeys(['process', 'database', 'queue', 'worker'], 'up'),
        'research_execution': 'unconfigured'})
    item.ready(CURRENT)


@pytest.mark.parametrize('value', ['main', 'a' * 39, 'A' * 40, '../main', 'c' * 40 + '\n', None])
def test_only_exact_sha_accepted(value):
    with pytest.raises(release.ReleaseError):
        release.Release(value)


@pytest.mark.parametrize('mode,path', [('120000', 'apps/api/Dockerfile'), ('100644', 'apps/api/../escape'),
                                     ('160000', 'apps/api/submodule')])
def test_api_context_rejects_nonregular_and_traversal(tmp_path, mode, path):
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        return f'{mode} blob abc\t{path}\0'.encode()
    item = release.Release(CURRENT, base=tmp_path, command=command)
    with pytest.raises(release.ReleaseError, match='Unsafe API context'):
        item.extract(tmp_path)
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())


def test_api_context_limits_size_before_reading_blob(tmp_path):
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        return b'100644 blob abc\tapps/api/Dockerfile\0' if 'ls-tree' in argv else b'8388609'
    item = release.Release(CURRENT, base=tmp_path, command=command)
    with pytest.raises(release.ReleaseError, match='exceeds limits'):
        item.extract(tmp_path)
    assert len(calls) == 2
    assert not list(tmp_path.iterdir())


def test_real_atomic_evidence_replaces_complete_file_and_cleans_temporary(tmp_path):
    path = tmp_path / 'receipt.json'
    release.atomic_json(path, {'old': True})
    release.atomic_json(path, {'new': True})
    assert json.loads(path.read_text()) == {'new': True}
    assert path.stat().st_mode & 0o077 == 0
    assert list(tmp_path.iterdir()) == [path]


def test_subprocess_exception_is_generic_without_captured_output(monkeypatch):
    def fail(*args, **kwargs):
        raise release.subprocess.CalledProcessError(1, 'docker', output=b'private-token', stderr=b'postgres://secret')
    monkeypatch.setattr(release.subprocess, 'run', fail)
    with pytest.raises(release.ReleaseError) as result:
        release.run(['docker', 'test'])
    assert str(result.value) == 'Release command failed'


def test_postrename_fsync_failure_restores_exact_previous_success_pointer(operation, monkeypatch):
    original = {'revision': PREVIOUS, 'schema': release.SCHEMA, 'backup': 'old-private.pgdump'}
    path = operation / 'runtime-success.json'
    release.atomic_json(path, original)
    actual = release.atomic_json
    def postrename_failure(path, value):
        actual(path, value)
        if value['revision'] == CURRENT:
            raise OSError('Synthetic directory fsync failure after rename')
    monkeypatch.setattr(release, 'atomic_json', postrename_failure)
    item = Controlled(operation)
    with pytest.raises(release.ReleaseError, match='previous service restored'):
        item.deploy()
    assert json.loads(path.read_text()) == original
    assert ('rollback-ready', PREVIOUS) in item.events


def test_failed_previous_runtime_readiness_stops_previous_api_worker(operation):
    item = Controlled(operation, fault='ready')
    def not_ready(revision):
        raise release.ReleaseError('Readiness failed')
    item.ready = not_ready
    with pytest.raises(release.ReleaseError, match='Rollback failed'):
        item.deploy()
    assert ('stop', PREVIOUS, ('stop', 'api', 'worker'), False) in item.events
    assert item.events[-1] == ('stop', CURRENT, ('stop', 'api', 'worker'), False)
    assert not (operation / 'runtime-success.json').exists()


@pytest.mark.parametrize('body,exit_code,limit,valid', [
    (b'PGDMP-complete', 0, 1000, True),
    (b'PGDMP-partial', 1, 1000, False),
    (b'not-an-archive', 0, 1000, False),
    (b'PGDMP-too-many-bytes', 0, 8, False),
])
def test_backup_real_subprocess_pipe_archive_bounds_and_private_cleanup(tmp_path, monkeypatch, body, exit_code, limit, valid):
    # Root ownership metadata is simulated; real child pipe/files/fsync/cleanup
    # are exercised. This is not a PostgreSQL dump or Hetzner ownership proof.
    folder = tmp_path / 'backups'
    folder.mkdir(mode=0o700)
    actual_stat = Path.lstat
    def root_metadata(path):
        value = actual_stat(path)
        if path == folder:
            values = list(value)
            values[4] = 0
            return os.stat_result(values)
        return value
    monkeypatch.setattr(Path, 'lstat', root_metadata)
    original_popen = release.subprocess.Popen
    calls = []
    def child(argv, **kwargs):
        calls.append(argv)
        code = f'import os;os.write(1,{body!r});raise SystemExit({exit_code})'
        return original_popen([sys.executable, '-c', code], **kwargs)
    monkeypatch.setattr(release.subprocess, 'Popen', child)
    monkeypatch.setattr(release, 'BACKUP_LIMIT', limit)
    item = release.Release(CURRENT, base=tmp_path)
    if valid:
        name = item.backup()
        archive = folder / name
        manifest = json.loads(archive.with_suffix('.json').read_text())
        assert archive.read_bytes() == body
        assert manifest['bytes'] == len(body)
        assert manifest['sha256'] == release.hashlib.sha256(body).hexdigest()
        assert archive.stat().st_mode & 0o077 == 0
    else:
        with pytest.raises(release.ReleaseError):
            item.backup()
        assert not list(folder.iterdir())
    assert len(calls) == 1
    assert 'pg_dump --format=custom' in calls[0][-1]
    assert '--no-owner' not in calls[0][-1] and '--no-acl' not in calls[0][-1]
    assert '/run/secrets/postgres-password' in calls[0][-1]


def test_previous_dangling_symlink_is_rejected_not_legacy_fallback(tmp_path):
    (tmp_path / 'runtime-success.json').symlink_to(tmp_path / 'missing')
    with pytest.raises(release.ReleaseError, match='Unsafe administrator file'):
        release.Release(CURRENT, base=tmp_path).previous()


def test_compose_ignores_ambient_docker_git_and_secret_authority(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKER_HOST', 'tcp://untrusted.invalid:2375')
    monkeypatch.setenv('GIT_SSH_COMMAND', 'untrusted-command')
    monkeypatch.setenv('GEMINI_API_KEY', 'private-value')
    calls = []
    def command(argv, **kwargs):
        calls.append((argv, kwargs))
        return b''
    item = release.Release(CURRENT, base=tmp_path, command=command)
    item.compose(CURRENT, 'stop', 'api', 'worker')
    assert calls[0][1]['env'] == dict(release.COMMAND_ENVIRONMENT, APP_REVISION=CURRENT)
    assert 'untrusted' not in str(calls) and 'private-value' not in str(calls)


def test_postrename_failure_restores_pointer_even_when_previous_migration_denies(operation, monkeypatch):
    original = {'revision': PREVIOUS, 'schema': release.SCHEMA, 'backup': 'original-private.pgdump'}
    path = operation / 'runtime-success.json'
    release.atomic_json(path, original)
    actual = release.atomic_json
    def postrename_failure(path, value):
        actual(path, value)
        if value['revision'] == CURRENT:
            raise OSError('Synthetic postrename fsync failure')
    monkeypatch.setattr(release, 'atomic_json', postrename_failure)
    item = Controlled(operation)
    original_migrate = item.migrate
    def deny_previous(revision):
        if revision == PREVIOUS:
            raise release.ReleaseError('Unsafe previous actual ACL')
        original_migrate(revision)
    item.migrate = deny_previous
    with pytest.raises(release.ReleaseError, match='Rollback failed'):
        item.deploy()
    assert json.loads(path.read_text()) == original
    assert not any(e[0] == 'application-up' and e[1] == PREVIOUS for e in item.events)
    assert item.events[-1] == ('stop', CURRENT, ('stop', 'api', 'worker'), False)


@pytest.mark.parametrize('content,accepted', [(b'fixture-password', True), (b'fixture-password\n', True), (b'', False)])
def test_backup_actual_shell_accepts_optional_lf_private_file_contract(tmp_path, monkeypatch, content, accepted):
    # Capture the production backup shell, then exercise its actual sh -eu FILE
    # intake. Only pg_dump and the fixed secret path are replaced by local fixtures.
    secret = tmp_path / 'fixture-password'
    secret.write_bytes(content)
    folder = tmp_path / 'backups'
    folder.mkdir(mode=0o700)
    actual_stat = Path.lstat
    def root_metadata(path):
        value = actual_stat(path)
        if path == folder:
            fields = list(value)
            fields[4] = 0
            return os.stat_result(fields)
        return value
    monkeypatch.setattr(Path, 'lstat', root_metadata)
    captured = []
    def no_dump(argv, **kwargs):
        captured.append(argv[-1])
        raise OSError('Capture only')
    monkeypatch.setattr(release.subprocess, 'Popen', no_dump)
    with pytest.raises(OSError):
        release.Release(CURRENT, base=tmp_path).backup()
    script = captured[0].split('exec pg_dump', 1)[0]
    script = script.replace('/run/secrets/postgres-password', shlex.quote(str(secret)))
    script += 'test "$PGPASSWORD" = fixture-password'
    # Restore actual Popen because subprocess.run uses it internally.
    monkeypatch.undo()
    result = release.subprocess.run(['sh', '-eu', '-c', script], capture_output=True, timeout=2)
    assert (result.returncode == 0) is accepted
    assert result.stdout == result.stderr == b''
