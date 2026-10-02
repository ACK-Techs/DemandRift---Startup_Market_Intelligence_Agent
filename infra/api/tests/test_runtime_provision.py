"""Secret producer boundaries; local ownership simulation is explicit."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'runtime_provision.py'
SPEC = importlib.util.spec_from_file_location('runtime_provision', SOURCE)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


@pytest.mark.parametrize('raw', [b'', b' ', b'a b', b'a\r\n', b'a\n\n', b'a\t',
                                 b'a\x00', b'\x7f', b'\xff', b'x' * 4097,
                                 b'x' * 4098, 'synthetic-key', None])
def test_bad_key_never_creates_credentials(raw, monkeypatch):
    monkeypatch.setattr(p.secrets, 'token_hex', lambda _: pytest.fail('Invalid key generated credentials'))
    with pytest.raises(p.ProvisionError):
        p.documents(raw)


@pytest.mark.parametrize('raw', [b'synthetic-key', b'synthetic-key\n', b'x' * 4096,
                                 b'x' * 4096 + b'\n'])
def test_valid_key_bare_or_final_lf_and_max_boundary(raw):
    assert p.documents(raw)['gemini-api-key'] == raw.rstrip(b'\n')


def test_distinct_credentials_exact_endpoints_and_safe_redis_acl():
    from urllib.parse import urlsplit
    import hashlib
    values = p.documents(b'synthetic-key')
    assert set(values) == p.APPLICATION_NAMES | p.DATABASE_NAMES
    app = urlsplit(values['application-database-url'].decode())
    admin = urlsplit(values['admin-database-url'].decode())
    broker = urlsplit(values['broker-url'].decode())
    assert (app.hostname, app.port, app.path) == (admin.hostname, admin.port, admin.path) == ('postgres', 5432, '/demandrift')
    assert (app.username, admin.username) == ('demandrift_app', 'demandrift_admin')
    assert (broker.username, broker.hostname, broker.port, broker.path) == ('demandrift', 'redis', 6379, '/0')
    assert admin.password.encode() == values['postgres-password']
    assert broker.password.encode() == values['redis-password']
    assert len({app.password, admin.password, broker.password}) == 3
    assert all(len(x) == 64 and set(x) <= set('0123456789abcdef') for x in (app.password, admin.password, broker.password))
    config = values['redis-config'].decode()
    assert broker.password not in config
    assert '#' + hashlib.sha256(broker.password.encode()).hexdigest() in config
    assert 'user default off\n' in config and '~demandrift:* &demandrift:*' in config
    assert 'appendonly yes\nappendfsync everysec\nsave ""\n' in config
    commands = set(config.splitlines()[-1].split()[5:])
    assert {'+ping', '+multi', '+exec', '+brpop', '+hset', '+zadd', '+evalsha', '+script|load'} <= commands
    assert not any(x in commands for x in ['+@all', '+@admin', '+flushall', '+flushdb', '+config', '+acl', '+shutdown'])


@pytest.fixture
def filesystem(tmp_path, monkeypatch):
    # Unit ownership is simulated on macOS/non-root CI. File creation, content,
    # modes, collision preservation and cleanup use the actual local filesystem.
    monkeypatch.setattr(p, 'require_directory', lambda _: None)
    owners = []
    monkeypatch.setattr(p.os, 'fchown', lambda fd, uid, gid: owners.append((uid, gid)))
    if sys.platform != 'linux':
        class Rename:
            def __call__(self, source_fd, source, target_fd, target, flags):
                assert source_fd == target_fd == -100 and flags == 1
                if os.path.lexists(target):
                    return -1
                os.rename(source, target)
                return 0
        class Libc:
            renameat2 = Rename()
        monkeypatch.setattr(p.ctypes, 'CDLL', lambda *a, **kw: Libc())
    return tmp_path / 'runtime', owners


def test_actual_file_modes_names_contents_and_uid_assignment(filesystem):
    target, owners = filesystem
    p.provision(target, b'synthetic-key\n')
    assert set(x.name for x in target.iterdir()) == p.APPLICATION_NAMES | p.DATABASE_NAMES
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert owners.count((10001, 10001)) == 4 and owners.count((999, 999)) == 3
    for file in target.iterdir():
        assert stat.S_IMODE(file.stat().st_mode) == 0o400
        assert file.stat().st_nlink == 1 and not file.is_symlink()
    assert (target / 'gemini-api-key').read_bytes() == b'synthetic-key'
    assert list(target.parent.glob('.runtime-secrets-*')) == []


@pytest.mark.parametrize('kind', ['directory', 'file', 'dangling-link'])
def test_existing_target_never_replaced_or_rotated(filesystem, kind, monkeypatch):
    target, _ = filesystem
    if kind == 'directory':
        target.mkdir()
        (target / 'original').write_text('keep')
    elif kind == 'file':
        target.write_text('keep')
    else:
        target.symlink_to(target.parent / 'missing')
    monkeypatch.setattr(p, 'documents', lambda _: pytest.fail('Existing credentials generated replacements'))
    with pytest.raises(p.ProvisionError):
        p.provision(target, b'synthetic-key')
    if kind == 'directory':
        assert (target / 'original').read_text() == 'keep'
    elif kind == 'file':
        assert target.read_text() == 'keep'
    else:
        assert target.is_symlink()


def test_no_replace_primitive_protects_racing_empty_target(filesystem, monkeypatch):
    target, _ = filesystem
    original = p.publish
    def race(staging, destination):
        destination.mkdir(mode=0o700)
        original(staging, destination)
    monkeypatch.setattr(p, 'publish', race)
    with pytest.raises(p.ProvisionError):
        p.provision(target, b'synthetic-key')
    assert target.is_dir() and list(target.iterdir()) == []
    assert list(target.parent.glob('.runtime-secrets-*')) == []


def test_prepublication_file_failure_cleans_only_owned_staging(filesystem, monkeypatch):
    target, _ = filesystem
    neighbor = target.parent / 'unrelated'
    neighbor.write_text('keep')
    original = p.write_file
    count = 0
    def failing(path, data, uid):
        nonlocal count
        count += 1
        if count == 3:
            raise OSError('synthetic-private-error-must-not-log')
        return original(path, data, uid)
    monkeypatch.setattr(p, 'write_file', failing)
    with pytest.raises(OSError):
        p.provision(target, b'synthetic-key')
    assert not target.exists() and neighbor.read_text() == 'keep'
    assert list(target.parent.glob('.runtime-secrets-*')) == []


def test_postpublication_fsync_failure_preserves_complete_target(filesystem, monkeypatch):
    target, _ = filesystem
    original = p.fsync_directory
    def failing(path):
        if path == target.parent:
            raise OSError('synthetic-fsync-fault')
        original(path)
    monkeypatch.setattr(p, 'fsync_directory', failing)
    with pytest.raises(OSError):
        p.provision(target, b'synthetic-key')
    assert set(x.name for x in target.iterdir()) == p.APPLICATION_NAMES | p.DATABASE_NAMES
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    with pytest.raises(p.ProvisionError):
        p.provision(target, b'replacement-key')
    assert (target / 'gemini-api-key').read_bytes() == b'synthetic-key'


@pytest.mark.parametrize('mode,uid', [(0o777, 0), (0o775, 0), (0o755, 10001), (0o700, 999)])
def test_unsafe_ancestor_metadata_rejected(tmp_path, mode, uid, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(p.Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | mode, st_uid=uid))
    with pytest.raises(p.ProvisionError):
        p.require_directory(tmp_path)


def test_symlink_ancestor_rejected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(p.Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0))
    with pytest.raises(p.ProvisionError):
        p.require_directory(tmp_path)


@pytest.mark.parametrize('mode', [0o755, 0o700])
def test_normal_root_owned_ancestor_modes_accepted(tmp_path, mode, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(p.Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | mode, st_uid=0))
    p.require_directory(tmp_path)


@pytest.mark.parametrize('arguments,uid', [(['synthetic-key'], 0), ([], 10001)])
def test_cli_denies_key_argv_nonroot_without_consuming_stdin(arguments, uid, monkeypatch, capsys):
    monkeypatch.setattr(p.os, 'getuid', lambda: uid)
    class NoRead:
        def read(self, _):
            pytest.fail('Unauthorized CLI consumed key')
    monkeypatch.setattr(p.sys, 'stdin', type('Stdin', (), {'buffer': NoRead()})())
    assert p.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == 'Runtime secret provision unavailable\n'


def test_existing_cli_target_denies_before_stdin(filesystem, monkeypatch, capsys):
    target, _ = filesystem
    target.mkdir()
    monkeypatch.setattr(p, 'TARGET', target)
    monkeypatch.setattr(p.os, 'getuid', lambda: 0)
    monkeypatch.setattr(p, 'deployment_lock', contextlib.nullcontext)
    class NoRead:
        def read(self, _):
            pytest.fail('Existing target consumed key')
    monkeypatch.setattr(p.sys, 'stdin', type('Stdin', (), {'buffer': NoRead()})())
    assert p.main([]) == 1
    assert capsys.readouterr().err == 'Runtime secret provision unavailable\n'


def test_cli_success_has_no_key_credential_path_or_environment_output(filesystem, monkeypatch, capsys):
    target, _ = filesystem
    monkeypatch.setattr(p, 'TARGET', target)
    monkeypatch.setattr(p.os, 'getuid', lambda: 0)
    monkeypatch.setattr(p, 'deployment_lock', contextlib.nullcontext)
    monkeypatch.setattr(p.sys, 'stdin', type('Stdin', (), {'buffer': io.BytesIO(b'synthetic-key\n')})())
    before = dict(os.environ)
    previous_umask = os.umask(0o077)
    try:
        assert p.main([]) == 0
    finally:
        os.umask(previous_umask)
    output = capsys.readouterr()
    assert output.out == 'Runtime secret files provisioned; verify private mounts before release\n'
    assert output.err == '' and dict(os.environ) == before
