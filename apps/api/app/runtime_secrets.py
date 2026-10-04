"""Bounded runtime-only credentials; diagnostics never include paths or values."""

import os
from pathlib import Path
import stat


class RuntimeSecretError(ValueError):
    pass


def _open_no_follow(path: Path) -> int:
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:-1]:
            following = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=directory)
            os.close(directory)
            directory = following
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                       dir_fd=directory)
    finally:
        os.close(directory)


def runtime_secret(name: str, *, allow_environment: bool = True) -> str:
    if (type(allow_environment) is not bool
            or name not in ("DATABASE_URL", "DEMANDRIFT_BROKER_URL", "GEMINI_API_KEY", "DEMANDRIFT_BUDGET_SUITE_ID")):
        raise RuntimeSecretError("Supported backend credential required")
    try:
        value, filename = os.environ.get(name), os.environ.get(name + "_FILE")
        if filename is not None:
            if value is not None:
                raise ValueError()
            path = Path(filename)
            if not path.is_absolute() or path.resolve(strict=True) != path:
                raise ValueError()
            fd = _open_no_follow(path)
            try:
                before = os.fstat(fd)
                if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                        or stat.S_IMODE(before.st_mode) not in (0o400, 0o600)
                        or before.st_uid not in (0, os.geteuid())
                        or not 1 <= before.st_size <= 4096):
                    raise ValueError()
                raw = os.read(fd, 4097)
                after = os.fstat(fd)
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError()
                if len(raw) != before.st_size:
                    raise ValueError()
                value = raw.removesuffix(b"\n").decode("ascii")
            finally:
                os.close(fd)
        elif not allow_environment or value is None:
            raise ValueError()
        if (type(value) is not str or not 1 <= len(value) <= 4096
                or not value.isascii() or any(not 33 <= ord(char) <= 126 for char in value)):
            raise ValueError()
        return value
    except (OSError, ValueError, UnicodeError, RuntimeError):
        raise RuntimeSecretError("Explicit private backend runtime credential required") from None
