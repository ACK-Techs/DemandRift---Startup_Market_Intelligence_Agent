"""Private, owner-scoped atomic capture storage. Hash equality grants no access."""
import hashlib
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

class ArtifactStorageError(RuntimeError):
    pass


class RawStorage:
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute() or '..' in self.root.parts:
            raise ArtifactStorageError('Canonical artifact root required')

    def _directory(self, parts, create=False):
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for name in [*self.root.parts[1:], *parts]:
                if create:
                    try:
                        os.mkdir(name, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            if stat.S_IMODE(os.fstat(fd).st_mode) & 0o077:
                raise ArtifactStorageError('Private artifact directory required')
            return fd
        except Exception:
            os.close(fd)
            raise ArtifactStorageError('Artifact directory unavailable') from None

    @staticmethod
    def _scope(owner, project, research, artifact):
        if any(type(value) is not UUID for value in (owner, project, research, artifact)):
            raise ArtifactStorageError('Resolved artifact scope required')
        return [str(owner), str(project), str(research)], str(artifact)

    def put(self, owner, project, research, artifact, content):
        parts, name = self._scope(owner, project, research, artifact)
        if type(content) is not bytes or not 0 < len(content) <= 2_000_000:
            raise ArtifactStorageError('Bounded capture required')
        fd = self._directory(parts, create=True)
        temporary = '.' + str(uuid4())
        try:
            try:
                existing = self.read(owner, project, research, artifact, hashlib.sha256(content).hexdigest(), len(content))
                if existing != content:
                    raise ArtifactStorageError('Immutable capture differs')
                return '/'.join([*parts, name])
            except FileNotFoundError:
                pass
            target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(target, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            # link is atomic and does not replace a concurrently written capture.
            try:
                os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            except FileExistsError:
                self.read(owner, project, research, artifact, hashlib.sha256(content).hexdigest(), len(content))
            os.fsync(fd)
            return '/'.join([*parts, name])
        finally:
            try:
                os.unlink(temporary, dir_fd=fd)
            except FileNotFoundError:
                pass
            os.close(fd)

    def read(self, owner, project, research, artifact, digest, size):
        parts, name = self._scope(owner, project, research, artifact)
        fd = self._directory(parts)
        try:
            source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(source, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size or info.st_size > 2_000_000 or stat.S_IMODE(info.st_mode) & 0o077:
                    raise ArtifactStorageError('Capture integrity differs')
                content = stream.read(2_000_001)
            if hashlib.sha256(content).hexdigest() != digest:
                raise ArtifactStorageError('Capture hash differs')
            return content
        finally:
            os.close(fd)
