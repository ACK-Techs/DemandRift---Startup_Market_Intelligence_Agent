"""Lazy private FILE credential in an owned, deadline-bounded child process."""

import asyncio
import math
import os
from pathlib import Path
import sys
import time

from app.runtime_secrets import RuntimeSecretError

_API_ROOT = str(Path(__file__).resolve().parents[1])
_READER = (
    "import sys; sys.path.insert(0, " + repr(_API_ROOT) + "); "
    "from app.runtime_secrets import runtime_secret; "
    "sys.stdout.buffer.write(runtime_secret('GEMINI_API_KEY', "
    "allow_environment=False).encode('ascii'))"
)
MAX_KEY_READ_SECONDS = 5


async def load_gemini_key(absolute_monotonic_deadline):
    """Read no environment credential, print no diagnostic, kill/reap on exit.

    The child gets only a FILE pointer. Its fixed reader outputs at most 4096
    private bytes; no caller-supplied code or executable is accepted.
    """
    if (type(absolute_monotonic_deadline) not in (int, float)
            or not math.isfinite(absolute_monotonic_deadline)
            or absolute_monotonic_deadline <= time.monotonic()):
        raise RuntimeSecretError("Private backend credential unavailable")
    filename = os.environ.get("GEMINI_API_KEY_FILE")
    if os.environ.get("GEMINI_API_KEY") is not None or filename is None:
        raise RuntimeSecretError("Private backend credential unavailable")
    deadline = min(absolute_monotonic_deadline, time.monotonic() + MAX_KEY_READ_SECONDS)
    process = None
    try:
        async with asyncio.timeout_at(deadline):
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-S", "-c", _READER,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env={"GEMINI_API_KEY_FILE": filename}, limit=4097,
            )
            raw, _ = await process.communicate()
        if process.returncode != 0 or not 16 <= len(raw) <= 512:
            raise ValueError()
        value = raw.decode("ascii")
        if any(not 33 <= ord(char) <= 126 for char in value):
            raise ValueError()
        return value
    except asyncio.CancelledError:
        raise
    except Exception:
        raise RuntimeSecretError("Private backend credential unavailable") from None
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            # SIGKILL ends this fixed child; complete its owned pipe/reaping
            # even when the generation task has already been cancelled.
            reaped = asyncio.create_task(process.communicate())
            while not reaped.done():
                try:
                    await asyncio.shield(reaped)
                except asyncio.CancelledError:
                    continue
            reaped.result()
