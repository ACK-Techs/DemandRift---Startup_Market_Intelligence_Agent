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


@pytest.mark.parametrize('schema', ['20261002_0008', '20261002_0009'])
def test_phase1_release_accepts_explicit_previous_eight_or_nine_pointer(tmp_path, monkeypatch, schema):
    pointer = {'revision': PREVIOUS, 'schema': schema, 'backup': 'private.pgdump'}
    (tmp_path / 'runtime-success.json').write_text(json.dumps(pointer))
    # Isolate pointer version parsing; native administrator FILE checks have separate controls.
    monkeypatch.setattr(release, 'private_file', lambda path: path.lstat())
    assert release.SCHEMA == '20261003_0010'
    assert release.Release(CURRENT, base=tmp_path).previous() == (PREVIOUS, False)


@pytest.mark.parametrize('schema', ['20261001_0007', '20261002_0010', None, 9])
def test_phase1_release_rejects_unsupported_previous_pointer_schema(tmp_path, monkeypatch, schema):
    (tmp_path / 'runtime-success.json').write_text(json.dumps(
        {'revision': PREVIOUS, 'schema': schema, 'backup': 'private.pgdump'}))
    monkeypatch.setattr(release, 'private_file', lambda path: path.lstat())
    with pytest.raises(release.ReleaseError, match='Invalid previous runtime state'):
        release.Release(CURRENT, base=tmp_path).previous()


def test_release_children_use_fixed_administrator_home_without_ambient_secrets(monkeypatch):
    monkeypatch.setenv('HOME', '/untrusted-home')
    monkeypatch.setenv('DOCKER_CONFIG', '/untrusted-docker-config')
    monkeypatch.setenv('HTTPS_PROXY', 'http://untrusted-proxy.invalid')
    monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-private-canary')
    calls = []
    def command(argv, **kwargs):
        calls.append((argv, kwargs))
        return type('Result', (), {'stdout': b'bounded-public-output'})()
    monkeypatch.setattr(release.subprocess, 'run', command)
    assert release.run(['docker', 'version']) == b'bounded-public-output'
    assert calls[0][1]['env'] == {
        'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root',
        'GIT_TERMINAL_PROMPT': '0', 'LANG': 'C.UTF-8',
    }
    assert calls[0][1]['stdin'] is release.subprocess.DEVNULL
    assert calls[0][1]['check'] is True


def test_actual_child_observes_fixed_home_without_ambient_provider_value(monkeypatch):
    monkeypatch.setenv('HOME', '/untrusted-home')
    monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-private-canary')
    observed = json.loads(release.run([
        sys.executable, '-I', '-S', '-c',
        "import json,os; print(json.dumps({'home':os.environ.get('HOME'),"
        "'providerPresent':'GEMINI_API_KEY' in os.environ}))",
    ]))
    assert observed == {'home': '/root', 'providerPresent': False}


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

    def restore_database(self, backup, schema):
        self.step('restore-database',backup,schema)

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
    monkeypatch.setattr(item, 'budget_digest', lambda *args: 'b'*64)
    if valid:
        # This existing test isolates the PostgreSQL dump pipe; artifact backup
        # integrity/restore has a separate end-to-end regression.
        monkeypatch.setattr(item,'backup_artifacts',lambda _: {'archive':'fixture.tar','sha256':'e'*64,'bytes':0})
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


def test_complete_backup_works_without_python311_file_digest(tmp_path, monkeypatch):
    monkeypatch.delattr(release.hashlib, 'file_digest', raising=False)
    body = b'PGDMP' + b'x' * 65536 + b'last-block'
    test_backup_real_subprocess_pipe_archive_bounds_and_private_cleanup(
        tmp_path, monkeypatch, body, 0, 70000, True)


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
    monkeypatch.setattr(release.Release, 'budget_digest', lambda *args: 'b'*64)
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


def test_postmigration_failure_restores_verified_snapshot_before_old_image(operation):
    (operation/'runtime-success.json').write_text(json.dumps({'revision':PREVIOUS,'schema':'20261002_0008','backup':'prior.pgdump'}))
    item=Controlled(operation,fault='ready')
    with pytest.raises(release.ReleaseError,match='previous service restored'):
        item.deploy()
    names=[event[0] for event in item.events]
    assert names.index('restore-database')<names.index('rollback-revalidation')
    assert ('restore-database','private.pgdump','20261002_0008') in item.events
    assert json.loads((operation/'runtime-success.json').read_text())['revision']==PREVIOUS


def test_database_rollback_validates_archive_and_schema_before_preserving_name_swap(operation,monkeypatch):
    import hashlib
    import importlib.util
    module_spec=importlib.util.spec_from_file_location('runtime_restore',Path(__file__).resolve().parents[1]/'runtime_restore.py')
    restore=importlib.util.module_from_spec(module_spec);sys.modules['runtime_restore']=restore;module_spec.loader.exec_module(restore)
    monkeypatch.setattr(release,'private_file',lambda path:path.lstat());monkeypatch.setattr(restore,'private_file',lambda path:path.lstat())
    folder=operation/'backups';folder.mkdir();archive=folder/'before.pgdump';archive.write_bytes(b'PGDMP-synthetic-control')
    manifest=folder/'before.json';manifest.write_text(json.dumps({'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'budget_digest':'b'*64}))
    events=[]
    def command(argv,**kwargs):
        events.append(argv[-1]);return b'20261002_0008\n' if 'SELECT version_num' in argv[-1] else b''
    def process(argv,**kwargs):
        events.append(argv[-1]);assert kwargs['stdin'].read()==archive.read_bytes()
    monkeypatch.setattr(release.subprocess,'run',process)
    item=release.Release(CURRENT,base=operation,command=command)
    monkeypatch.setattr(item,'budget_digest',lambda *args:'b'*64)
    item.restore_database(archive.name,'20261002_0008')
    assert 'createdb' in events[0] and 'pg_restore --exit-on-error' in events[1]
    assert 'SELECT version_num' in events[2]
    assert 'BEGIN; ALTER DATABASE demandrift RENAME TO demandrift_retained_' in events[3]
    assert 'COMMIT;' in events[3] and all('DROP DATABASE' not in event for event in events)
    events.clear();archive.write_bytes(b'PGDMP-corrupted')
    with pytest.raises(release.ReleaseError,match='size differs|hash differs'):
        item.restore_database(archive.name,'20261002_0008')
    assert not events


def test_database_rollback_schema_mismatch_never_swaps_current_name(operation,monkeypatch):
    import hashlib
    import runtime_restore as restore
    monkeypatch.setattr(release,'private_file',lambda path:path.lstat());monkeypatch.setattr(restore,'private_file',lambda path:path.lstat())
    folder=operation/'backups';folder.mkdir();archive=folder/'before.pgdump';archive.write_bytes(b'PGDMP-synthetic-control')
    (folder/'before.json').write_text(json.dumps({'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'budget_digest':'b'*64}))
    events=[]
    def command(argv,**kwargs): events.append(argv[-1]);return b'20261003_0010\n'
    monkeypatch.setattr(release.subprocess,'run',lambda *args,**kwargs:None)
    monkeypatch.setattr(release.Release,'budget_digest',lambda *args:'b'*64)
    with pytest.raises(release.ReleaseError,match='Restored schema differs'):
        release.Release(CURRENT,base=operation,command=command).restore_database(archive.name,'20261002_0008')
    assert all('ALTER DATABASE' not in event for event in events)


@pytest.mark.parametrize('saved', [None, 'b'*64])
def test_rollback_never_erases_unrecorded_or_newer_budget(operation,monkeypatch,saved):
    import hashlib
    import runtime_restore as restore
    monkeypatch.setattr(release,'private_file',lambda path:path.lstat())
    monkeypatch.setattr(restore,'private_file',lambda path:path.lstat())
    folder=operation/'backups';folder.mkdir();archive=folder/'before.pgdump'
    archive.write_bytes(b'PGDMP-synthetic-control')
    record={'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size}
    if saved: record['budget_digest']=saved
    (folder/'before.json').write_text(json.dumps(record))
    calls=[]
    item=release.Release(CURRENT,base=operation,command=lambda argv,**kwargs:calls.append(argv))
    monkeypatch.setattr(item,'budget_digest',lambda *args:'c'*64)
    with pytest.raises(release.ReleaseError,match='budget state|Budget changed'):
        item.restore_database(archive.name,'20261002_0008')
    assert calls==[]  # No restore, name swap or old-image startup can erase the live ledger.
