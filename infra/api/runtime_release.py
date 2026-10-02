"""Administrator-installed, fixed-path coordinator; never loaded from fetched Git."""

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

BASE = Path('/opt/demandrift-api')
REPOSITORY = Path('/opt/demandrift-build/repository')
BUILD_LOCK = Path('/opt/demandrift-build/build.lock')
SCHEMA = '20261002_0008'
SHA = re.compile(r'[0-9a-f]{40}\Z')
BACKUP_LIMIT = 1024 ** 3
COMMAND_ENVIRONMENT = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                       'GIT_TERMINAL_PROMPT': '0', 'LANG': 'C.UTF-8'}


class ReleaseError(Exception):
    """Public errors intentionally contain no subprocess output or credentials."""


def archive_hash(source):
    """Portable SHA256 for the actual Python3.10 administrator runtime."""
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(65536), b''):
        digest.update(chunk)
    return digest.hexdigest()


def run(argv, *, timeout=180, env=None):
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                check=True, timeout=timeout,
                                env=COMMAND_ENVIRONMENT if env is None else env)
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise ReleaseError('Release command failed') from None


def private_file(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ReleaseError('Unsafe administrator file')


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.release-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(value, sort_keys=True) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(path, *, timeout=600):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ReleaseError('Unsafe administrator lock')
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ReleaseError('Administrator operation lock timed out') from None
                time.sleep(0.1)
        yield
    finally:
        os.close(fd)


class Release:
    def __init__(self, sha, *, base=BASE, repository=REPOSITORY,
                 command=run, read_ready=None):
        if type(sha) is not str or not SHA.fullmatch(sha):
            raise ReleaseError('Expected exact main revision')
        self.sha, self.base, self.repository = sha, Path(base), Path(repository)
        self.command = command
        self.read_ready = read_ready or self.http_ready

    def compose(self, revision, *arguments, legacy=False):
        if not SHA.fullmatch(revision):
            raise ReleaseError('Invalid runtime revision')
        compose = self.base / ('compose.yml' if legacy else 'runtime.compose.yml')
        env = dict(COMMAND_ENVIRONMENT, APP_REVISION=revision)
        return self.command(['docker', 'compose', '-p', 'demandrift-api', '-f', str(compose),
                             *arguments], timeout=180, env=env)

    def exact_main(self):
        self.command(['git', '-C', str(self.repository), 'fetch', '--depth=1', 'origin', 'main'])
        actual = self.command(['git', '-C', str(self.repository), 'rev-parse', 'FETCH_HEAD'])
        if actual.decode('ascii').strip() != self.sha:
            raise ReleaseError('Main advanced; select the accepted current revision')

    def extract(self, destination):
        entries = self.command(['git', '-C', str(self.repository), 'ls-tree', '-rz',
                                self.sha, '--', 'apps/api/']).split(b'\0')
        count = total = 0
        for entry in filter(None, entries):
            meta, raw_path = entry.split(b'\t', 1)
            mode, kind, blob = meta.split()
            try:
                relative = PurePosixPath(raw_path.decode('utf-8')).relative_to('apps/api')
            except (ValueError, UnicodeError):
                raise ReleaseError('Unsafe API context') from None
            if mode not in (b'100644', b'100755') or kind != b'blob' or '..' in relative.parts:
                raise ReleaseError('Unsafe API context')
            size = int(self.command(['git', '-C', str(self.repository), 'cat-file', '-s', blob.decode()]))
            count += 1
            total += size
            if size < 0 or size > 8 * 1024 ** 2 or total > 64 * 1024 ** 2 or count > 1000:
                raise ReleaseError('API context exceeds limits')
            data = self.command(['git', '-C', str(self.repository), 'cat-file', 'blob', blob.decode()])
            if len(data) != size:
                raise ReleaseError('API context changed')
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not (destination / 'Dockerfile').is_file():
            raise ReleaseError('Missing API Dockerfile')

    def build(self, context):
        self.command(['docker', 'build', '--target', 'test', '-t', f'demandrift-api-test:{self.sha}',
                      str(context)], timeout=600)
        self.command(['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                      '--security-opt=no-new-privileges', '--pids-limit=128', '--memory=512m',
                      '--cpus=1', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
                      f'demandrift-api-test:{self.sha}'], timeout=180)
        self.command(['docker', 'build', '--target', 'runtime', '--build-arg', f'APP_REVISION={self.sha}',
                      '--label', f'org.opencontainers.image.revision={self.sha}', '-t',
                      f'demandrift-api:{self.sha}', str(context)], timeout=600)

    def previous(self):
        runtime = self.base / 'runtime-success.json'
        if os.path.lexists(runtime):
            private_file(runtime)
            data = json.loads(runtime.read_text())
            if (type(data) is not dict or set(data) != {'revision', 'schema', 'backup'}
                    or type(data['revision']) is not str or not SHA.fullmatch(data['revision']) or data['schema'] != SCHEMA
                    or type(data['backup']) is not str):
                raise ReleaseError('Invalid previous runtime state')
            return data['revision'], False
        legacy = self.base / 'last-successful-sha'
        if os.path.lexists(legacy):
            private_file(legacy)
            revision = legacy.read_text().strip()
            if not SHA.fullmatch(revision):
                raise ReleaseError('Invalid previous legacy state')
            private_file(self.base / 'compose.yml')
            return revision, True
        raise ReleaseError('Existing service revision must be recorded before transition')

    def backup(self):
        folder = self.base / 'backups'
        folder.mkdir(mode=0o700, exist_ok=True)
        info = folder.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ReleaseError('Unsafe backup directory')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
        fd, name = tempfile.mkstemp(prefix=f'{stamp}-{self.sha}-', suffix='.pgdump', dir=folder)
        path = Path(name)
        # Password is read by the existing PostgreSQL UID inside its container;
        # never passed in argv, emitted by this process, or loaded into host env.
        argv = ['docker', 'compose', '-p', 'demandrift-api', '-f', str(self.base / 'runtime.compose.yml'),
                'exec', '-T', 'postgres', 'sh', '-eu', '-c',
                'IFS= read -r PGPASSWORD < /run/secrets/postgres-password || [ -n "$PGPASSWORD" ]; '
                'export PGPASSWORD; '
                'exec pg_dump --format=custom -U demandrift_admin -d demandrift']
        process = None
        try:
            with os.fdopen(fd, 'wb') as stream:
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL,
                                           env=dict(COMMAND_ENVIRONMENT, APP_REVISION=self.sha))
                deadline = time.monotonic() + 180
                size = 0
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or not selector.select(remaining):
                            raise ReleaseError('Backup exceeded deadline')
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > BACKUP_LIMIT:
                            raise ReleaseError('Backup exceeded byte limit')
                        stream.write(chunk)
                process.stdout.close()
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
                if process.returncode:
                    raise ReleaseError('Private backup failed')
                stream.flush()
                os.fsync(stream.fileno())
            with path.open('rb') as source:
                if source.read(5) != b'PGDMP':
                    raise ReleaseError('Invalid backup archive')
                source.seek(0)
                digest = archive_hash(source)
            atomic_json(path.with_suffix('.json'), {'revision': self.sha, 'archive': path.name,
                        'sha256': digest, 'bytes': path.stat().st_size,
                        'scope': 'database objects/data; role secrets and artifact volume require separate backups'})
            return path.name
        except BaseException:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            if process is not None and process.stdout is not None:
                process.stdout.close()
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def http_ready():
        # No redirect or proxy may move the fixed loopback readiness request.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open('http://127.0.0.1:18082/ready', timeout=12) as response:
            if response.status != 200:
                raise ReleaseError('Runtime is not ready')
            body = response.read(4097)
        if len(body) > 4096:
            raise ReleaseError('Invalid runtime readiness')
        return json.loads(body)

    def ready(self, revision):
        data = self.read_ready()
        if (type(data) is not dict or data.get('status') != 'ready'
                or data.get('revision') != revision
                or data.get('checks') != {'process': 'up', 'database': 'up', 'queue': 'up', 'worker': 'up'}):
            raise ReleaseError('Exact runtime dependencies are not ready')

    def migrate(self, revision):
        self.compose(revision, '--profile', 'operations', 'run', '--rm', '--no-deps', 'migrate')

    def rollback(self, previous, legacy):
        self.compose(self.sha, 'stop', 'api', 'worker')
        try:
            if legacy:
                self.compose(previous, 'up', '-d', '--wait', '--wait-timeout', '90', 'api', legacy=True)
            else:
                # Revalidate the actual schema/ACL using the previous accepted image.
                # A failed post-migration security check must never start old workers.
                self.migrate(previous)
                self.compose(previous, 'up', '-d', '--wait', '--wait-timeout', '90', 'api', 'worker')
                self.ready(previous)
        except BaseException:
            self.compose(previous, 'stop', *(['api'] if legacy else ['api', 'worker']), legacy=legacy)
            raise

    def restore_success_pointer(self, original):
        path = self.base / 'runtime-success.json'
        if original is not None:
            atomic_json(path, json.loads(original))
        else:
            path.unlink(missing_ok=True)
            directory = os.open(self.base, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def deploy(self):
        previous, legacy = self.previous()
        pointer = self.base / 'runtime-success.json'
        original = pointer.read_bytes() if pointer.exists() else None
        with tempfile.TemporaryDirectory(prefix='context-', dir=self.base) as temporary:
            with locked(BUILD_LOCK):
                self.exact_main()
                self.extract(Path(temporary))
            self.build(Path(temporary))
            with locked(BUILD_LOCK):
                self.exact_main()
                self.compose(self.sha, 'up', '-d', '--wait', '--wait-timeout', '90', 'postgres', 'redis')
                quiesced = False
                writing_receipt = False
                try:
                    # Once stop is attempted, a partially stopped service also
                    # requires rollback. Data volumes are never removed.
                    quiesced = True
                    self.compose(self.sha, 'stop', 'api', 'worker')
                    backup = self.backup()
                    self.migrate(self.sha)
                    self.compose(self.sha, 'up', '-d', '--wait', '--wait-timeout', '90', 'api', 'worker')
                    self.ready(self.sha)
                    writing_receipt = True
                    atomic_json(self.base / 'runtime-success.json',
                                {'revision': self.sha, 'schema': SCHEMA, 'backup': backup})
                except BaseException:
                    if quiesced:
                        try:
                            # A rename may already have published CURRENT before
                            # directory fsync failed. Restore the known previous
                            # success record even when rollback later denies the
                            # actual schema/ACL or cannot start old services.
                            if writing_receipt:
                                self.restore_success_pointer(original)
                            self.rollback(previous, legacy)
                        except BaseException:
                            try:
                                self.compose(self.sha, 'stop', 'api', 'worker')
                            finally:
                                raise ReleaseError('Rollback failed; application services require intervention') from None
                    raise ReleaseError('Release failed; previous service restored') from None


def main(arguments):
    try:
        if os.getuid() != 0 or len(arguments) != 1:
            raise ReleaseError('Administrator and one exact revision required')
        os.umask(0o077)
        for directory in (BASE, BASE / 'logs'):
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ReleaseError('Unsafe administrator directory')
        private_file(BASE / 'runtime.compose.yml')
        release = Release(arguments[0])
        with locked(BASE / 'deploy.lock'):
            release.deploy()
        print(f'SUCCESS runtime revision={release.sha} loopback=127.0.0.1:18082')
        return 0
    except (Exception, KeyboardInterrupt):
        print('Runtime release failed; consult private acceptance evidence', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
