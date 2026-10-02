"""Actual owned child processes and synthetic FILE credentials; no provider."""

import asyncio
import os
import time

import pytest

from app import gemini_runtime_key as key_reader
from app.runtime_secrets import RuntimeSecretError

SYNTHETIC = "synthetic-only-runtime-key-20261002"


@pytest.fixture
def credential(tmp_path, monkeypatch):
    file = tmp_path.resolve() / "synthetic-key"
    file.write_text(SYNTHETIC + "\n")
    file.chmod(0o600)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(file))
    return file


def test_actual_child_reads_private_synthetic_file_without_environment_value(credential, monkeypatch):
    monkeypatch.setenv("UNRELATED_PRIVATE_SENTINEL", "must-not-be-forwarded")
    reader = key_reader._READER
    monkeypatch.setattr(key_reader, "_READER", "import os; assert set(os.environ) <= "
        "{'GEMINI_API_KEY_FILE', 'LC_CTYPE', '__CF_USER_TEXT_ENCODING'}; " + reader)
    assert asyncio.run(key_reader.load_gemini_key(time.monotonic() + 2)) == SYNTHETIC


@pytest.mark.parametrize("content", [b"", b"x" * 15, b"x" * 513, b"x" * 4097,
                                       b"synthetic key with spaces", b"x" * 20 + b"\r\n"])
def test_invalid_synthetic_key_is_safe_and_has_no_value_in_exception(credential, content):
    credential.write_bytes(content)
    with pytest.raises(RuntimeSecretError) as error:
        asyncio.run(key_reader.load_gemini_key(time.monotonic() + 2))
    assert str(error.value) == "Private backend credential unavailable"
    assert str(credential) not in repr(error.value)


@pytest.mark.parametrize("kind", ["mode", "symlink", "hardlink"])
def test_child_retains_private_regular_nofollow_singlelink_contract(credential, monkeypatch, kind):
    if kind == "mode":
        credential.chmod(0o644)
    elif kind == "symlink":
        link = credential.with_name("synthetic-link")
        link.symlink_to(credential)
        monkeypatch.setenv("GEMINI_API_KEY_FILE", str(link))
    else:
        os.link(credential, credential.with_name("other-link"))
    with pytest.raises(RuntimeSecretError, match="Private backend credential unavailable"):
        asyncio.run(key_reader.load_gemini_key(time.monotonic() + 2))


@pytest.mark.parametrize("deadline", [True, 0, float("nan"), float("inf")])
def test_invalid_deadline_never_spawns_child(credential, monkeypatch, deadline):
    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration spawned a child")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(RuntimeSecretError):
        asyncio.run(key_reader.load_gemini_key(deadline))


@pytest.mark.parametrize("kind", ["raw", "missing", "ambiguous"])
def test_environment_credential_never_reaches_child(credential, monkeypatch, kind):
    if kind in ("raw", "ambiguous"):
        monkeypatch.setenv("GEMINI_API_KEY", SYNTHETIC)
    if kind in ("raw", "missing"):
        monkeypatch.delenv("GEMINI_API_KEY_FILE")
    async def forbidden(*args, **kwargs):
        pytest.fail("Environment credential spawned a child")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(RuntimeSecretError):
        asyncio.run(key_reader.load_gemini_key(time.monotonic() + 2))


@pytest.mark.parametrize("boundary", ["timeout", "cancel"])
def test_actual_blocked_child_is_killed_and_reaped(credential, monkeypatch, boundary):
    pidfile = credential.with_name("owned-reader-pid")
    monkeypatch.setattr(key_reader, "_READER",
        "import os,time; from pathlib import Path; "
        f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)")

    async def run():
        task = asyncio.create_task(key_reader.load_gemini_key(time.monotonic() + 0.35))
        for _ in range(100):
            if pidfile.exists():
                break
            await asyncio.sleep(0.003)
        assert pidfile.exists()
        if boundary == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(RuntimeSecretError):
                await task

    start = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - start < 1.5
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
