"""Trusted administrator first-install producer; values never enter argv or logs."""

import contextlib
import ctypes
import fcntl
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
import tempfile

TARGET = Path('/etc/demandrift/runtime')
LOCK = Path('/opt/demandrift-api/deploy.lock')
APPLICATION_NAMES = frozenset({'application-database-url', 'admin-database-url',
                               'broker-url', 'gemini-api-key'})
DATABASE_NAMES = frozenset({'postgres-password', 'redis-password', 'redis-config'})
REDIS_COMMANDS = (
    'ping select get set ttl expire pexpire del exists lpush rpush lpop rpop brpop '
    'llen lrange hset hget hdel hlen hgetall hincrby zadd zrem zrangebyscore '
    'zrevrangebyscore zcount zcard sadd srem smembers watch unwatch multi exec '
    'discard evalsha script|load publish subscribe unsubscribe psubscribe '
    'punsubscribe client|setname client|setinfo'
).split()


class ProvisionError(Exception):
    """Public failure deliberately excludes paths, values and underlying errors."""


def key_bytes(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= 4097:
        raise ProvisionError('Invalid key input')
    value = raw[:-1] if raw.endswith(b'\n') else raw
    if not 1 <= len(value) <= 4096 or any(byte < 33 or byte > 126 for byte in value):
        raise ProvisionError('Invalid key input')
    return value


def documents(key):
    key = key_bytes(key)
    admin, application, redis = (secrets.token_hex(32) for _ in range(3))
    redis_digest = hashlib.sha256(redis.encode('ascii')).hexdigest()
    return {
        'application-database-url': f'postgresql+psycopg://demandrift_app:{application}@postgres:5432/demandrift'.encode(),
        'admin-database-url': f'postgresql+psycopg://demandrift_admin:{admin}@postgres:5432/demandrift'.encode(),
        'broker-url': f'redis://demandrift:{redis}@redis:6379/0'.encode(),
        'gemini-api-key': key,
        'postgres-password': admin.encode(),
        'redis-password': redis.encode(),
        'redis-config': (
            'bind 0.0.0.0\nport 6379\nprotected-mode yes\ndir /data\n'
            'appendonly yes\nappendfsync everysec\nsave ""\n'
            'user default off\n'
            f'user demandrift on #{redis_digest} ~demandrift:* &demandrift:* '
            + ' '.join('+' + command for command in REDIS_COMMANDS) + '\n'
        ).encode(),
    }


def require_directory(path):
    if not path.is_absolute():
        raise ProvisionError('Unsafe administrator directory')
    for parent in (*reversed(path.parents), path):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise ProvisionError('Unsafe administrator directory')


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_file(path, data, uid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchown(stream.fileno(), uid, uid)
            os.fchmod(stream.fileno(), 0o400)
            os.fsync(stream.fileno())
    except BaseException:
        # Ownership changes do not remove the administrator's unlink authority.
        path.unlink(missing_ok=True)
        raise


def publish(staging, target):
    # Linux renameat2(RENAME_NOREPLACE) protects even against a process that
    # creates an empty target directory without taking the deployment lock.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                      ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(target), 1) != 0:
        raise ProvisionError('Secret publication unavailable')


def provision(target, key):
    """Caller holds the trusted deployment lock; no existing directory is adopted."""
    require_directory(target.parent)
    if os.path.lexists(target):
        raise ProvisionError('Existing runtime credentials require separate review')
    values = documents(key)
    staging = Path(tempfile.mkdtemp(prefix='.runtime-secrets-', dir=target.parent))
    try:
        os.chmod(staging, 0o700)
        for name, data in values.items():
            write_file(staging / name, data, 10001 if name in APPLICATION_NAMES else 999)
        fsync_directory(staging)
        # Both operations use the same Root-owned deployment lock. Recheck just
        # before publication; never replace/adopt a pre-existing secret directory.
        if os.path.lexists(target):
            raise ProvisionError('Existing runtime credentials require separate review')
        publish(staging, target)
        fsync_directory(target.parent)
    finally:
        # A post-rename fsync failure leaves a complete private directory in place
        # and reports failure. A retry refuses it instead of rotating credentials.
        if staging.exists():
            shutil.rmtree(staging)


@contextlib.contextmanager
def deployment_lock():
    require_directory(LOCK.parent)
    fd = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ProvisionError('Unsafe administrator lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def main(arguments):
    try:
        if os.getuid() != 0 or arguments:
            raise ProvisionError('Administrator stdin operation required')
        os.umask(0o077)
        with deployment_lock():
            require_directory(TARGET.parent)
            if os.path.lexists(TARGET):
                raise ProvisionError('Existing runtime credentials require separate review')
            provision(TARGET, sys.stdin.buffer.read(4098))
        print('Runtime secret files provisioned; verify private mounts before release')
        return 0
    except (Exception, KeyboardInterrupt):
        print('Runtime secret provision unavailable', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
