"""Real private filesystem/process crash checks; no database/provider calls."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from app import receipt_spool as module
from app.budget_contract import ResourceAmount
from app.db.budget_repository import AttemptReceipt
from app.gemini_contract import MODEL_ID
from app.gemini_transport import CompleteObservation, UnknownObservation
from app.job_budget_contract import AdmissionContext
from app.receipt_spool import (
    MAX_RECORD_BYTES,
    MAX_RESPONSE_BYTES,
    ReceiptBinding,
    ReceiptScope,
    ReceiptSpool,
    SpoolConfigurationError,
    SpoolConflict,
    SpoolCorrupt,
    SpoolError,
    SpoolNotFound,
    SpoolStorageError,
)

META = {
    "kind": "model",
    "operation_version": "compact-32k-estimate65536-totalpayload-v1",
    "provider": "developer",
    "model": MODEL_ID,
    "prompt_version": "v1",
    "schema_version": "1.0.0",
    "pricing_version": "v1",
}


def binding(scope=None, attempt=None, job=False):
    context = (
        AdmissionContext("job", uuid4(), 1, uuid4(), uuid4(), 1)
        if job
        else AdmissionContext("preparation", uuid4(), 1)
    )
    return ReceiptBinding(
        scope or ReceiptScope(uuid4(), uuid4(), uuid4()),
        attempt or uuid4(),
        context,
        "a" * 64,
        ResourceAmount(
            requests=1, bytes=MAX_RESPONSE_BYTES + 32768, tokens=1000, cost_picousd=1000
        ),
        dict(META),
    )


def observation(raw=b'{"private_output":"fixture only"}', status=200):
    return CompleteObservation(
        status, raw, len(raw), 15, hashlib.sha256(raw).hexdigest()
    )


def store(spool, value, data=None, **kwargs):
    return spool.store_complete(
        value,
        data or observation(),
        outgoing_bytes=kwargs.pop("outgoing_bytes", 10),
        response_limit_bytes=kwargs.pop("response_limit_bytes", MAX_RESPONSE_BYTES),
        **kwargs,
    )


def leaf(root, value):
    return (
        root
        / str(value.scope.user_id)
        / str(value.scope.project_id)
        / str(value.scope.research_id)
    )


def path(root, value, suffix="receipt"):
    return leaf(root, value) / f"{value.attempt_id}.{suffix}"


def actual(record):
    return ResourceAmount(
        requests=1,
        bytes=record.outgoing_bytes + record.observation.received_bytes,
        tokens=20,
        cost_picousd=20,
    )


def committed(record):
    return AttemptReceipt(
        record.binding.attempt_id,
        "settled",
        record.binding.reserved,
        actual(record),
        False,
    )


def test_raw_write_once_private_modes_and_restart(tmp_path):
    root, value = tmp_path / "spool", binding(job=True)
    data = observation(b"\xff\x00private output\n", 500)
    with ReceiptSpool(root) as spool:
        record = store(spool, value, data)
        assert record.observation == data and not record.acknowledged
        assert "private output" not in repr(record)
        assert store(spool, value, data) == record
        for location in (root, root / str(value.scope.user_id), leaf(root, value)):
            assert stat.S_IMODE(location.stat().st_mode) == 0o700
        assert stat.S_IMODE(path(root, value).stat().st_mode) == 0o600
        assert path(root, value).stat().st_nlink == 1
        raw = path(root, value).read_bytes()
        assert b"private output" in raw
        assert not any(
            label in raw
            for label in (b"headers", b"runtime_secret", b"canonical_body", b"api_key")
        )
    with ReceiptSpool(root) as restarted:
        assert restarted.read(value) == record
        assert restarted.pending(value.scope).items == (record,)
        assert restarted.pending(ReceiptScope(uuid4(), uuid4(), uuid4())).items == ()


def test_exact_conflict_metadata_copy_and_context(tmp_path):
    value = binding()
    metadata = dict(META)
    value = replace(value, metadata=metadata)
    metadata["prompt_version"] = "changed"
    assert value.metadata["prompt_version"] == "v1"
    with pytest.raises(TypeError):
        value.metadata["prompt_version"] = "other"
    with ReceiptSpool(tmp_path / "spool") as spool:
        store(spool, value)
        for data in (
            observation(b"different"),
            replace(observation(), status_code=201),
            replace(observation(), elapsed_ms=16),
        ):
            with pytest.raises(SpoolConflict):
                store(spool, value, data)
        for changed in (
            replace(value, input_fingerprint="b" * 64),
            replace(value, context=replace(value.context, brief_version=2)),
        ):
            with pytest.raises(SpoolConflict):
                spool.read(changed)
        with pytest.raises(SpoolConflict):
            store(spool, value, operation="count")


@pytest.mark.parametrize(
    "failure", ["status", "length", "hash", "cap", "counter", "unknown"]
)
def test_complete_bounds_fail_before_publication(tmp_path, failure):
    value, data, kwargs = binding(), observation(), {}
    if failure == "status":
        data = replace(data, status_code=True)
    elif failure == "length":
        data = replace(data, received_bytes=data.received_bytes + 1)
    elif failure == "hash":
        data = replace(data, response_sha256="b" * 64)
    elif failure == "cap":
        kwargs["response_limit_bytes"] = MAX_RESPONSE_BYTES + 1
    elif failure == "counter":
        kwargs["outgoing_bytes"] = True
    else:
        data = UnknownObservation("timeout", 200, 1, 10, "a" * 64)
    with ReceiptSpool(tmp_path / "spool") as spool:
        with pytest.raises(SpoolConfigurationError):
            store(spool, value, data, **kwargs)
        assert spool.pending(value.scope).items == ()


def test_exact_hard_cap_and_pinned_smaller_limit(tmp_path):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        record = store(spool, value, observation(b"z" * MAX_RESPONSE_BYTES))
        assert path(root, value).stat().st_size <= MAX_RECORD_BYTES
        assert record.observation.received_bytes == MAX_RESPONSE_BYTES
        with pytest.raises(SpoolConfigurationError):
            store(spool, binding(), observation(b"z" * 1025), response_limit_bytes=1024)


@pytest.mark.parametrize(
    "attack", ["root_symlink", "ancestor_symlink", "mode", "relative", "traversal"]
)
def test_root_symlink_modes_and_traversal(tmp_path, attack):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    if attack == "root_symlink":
        root = tmp_path / "linked"
        root.symlink_to(private, target_is_directory=True)
    elif attack == "ancestor_symlink":
        linked = tmp_path / "linked"
        linked.symlink_to(private, target_is_directory=True)
        root = linked / "spool"
    elif attack == "mode":
        os.chmod(private, 0o755)
        root = private
    elif attack == "relative":
        root = Path("relative")
    else:
        root = tmp_path / ".." / "traversal"
    with pytest.raises(SpoolConfigurationError):
        ReceiptSpool(root)


@pytest.mark.parametrize(
    "attack",
    [
        "record_symlink",
        "record_hardlink",
        "record_mode",
        "scope_symlink",
        "scope_mode",
        "lock_symlink",
        "ack_symlink",
    ],
)
def test_link_and_mode_attacks_fail_closed(tmp_path, attack):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        store(spool, value)
        location = path(root, value)
        if attack == "record_symlink":
            outside = tmp_path / "outside"
            outside.write_bytes(location.read_bytes())
            os.chmod(outside, 0o600)
            location.unlink()
            location.symlink_to(outside)
        elif attack == "record_hardlink":
            os.link(location, tmp_path / "outside")
        elif attack == "record_mode":
            os.chmod(location, 0o644)
        elif attack == "scope_symlink":
            old = leaf(root, value)
            saved = old.with_name("saved")
            old.rename(saved)
            old.symlink_to(saved, target_is_directory=True)
        elif attack == "scope_mode":
            os.chmod(leaf(root, value), 0o750)
        elif attack == "lock_symlink":
            location = leaf(root, value) / f".{value.attempt_id}.lock"
            location.unlink()
            location.symlink_to(tmp_path / "outside")
        else:
            path(root, value, "ack").symlink_to(tmp_path / "outside")
        with pytest.raises(SpoolError):
            spool.pending(value.scope)
        with pytest.raises(SpoolError):
            store(spool, value)


def test_corrupt_record_ack_and_orphan_fail_closed(tmp_path):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        store(spool, value)
        location = path(root, value)
        original = location.read_bytes()
        location.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with pytest.raises(SpoolCorrupt):
            spool.read(value)
        with pytest.raises(SpoolCorrupt):
            spool.pending(value.scope)
        location.write_bytes(original)
        marker = path(root, value, "ack")
        marker.write_bytes(b'{"unknown":true}')
        os.chmod(marker, 0o600)
        with pytest.raises(SpoolError):
            spool.pending(value.scope)
        location.unlink()
        with pytest.raises(SpoolCorrupt):
            spool.pending(value.scope)


def test_scoped_paging_callback_commit_order_and_ack_restart(tmp_path):
    root, value = tmp_path / "spool", binding()
    seen = []
    with ReceiptSpool(root) as spool:
        records = [
            store(spool, replace(value, attempt_id=UUID(int=i))) for i in range(1, 4)
        ]
        page = spool.pending(value.scope, limit=1)
        assert (
            page.items == (records[0],)
            and page.next_after_attempt_id == records[0].binding.attempt_id
        )
        assert spool.pending(
            value.scope, limit=1, after_attempt_id=page.next_after_attempt_id
        ).items == (records[1],)

        def commit(record):
            assert not path(root, record.binding, "ack").exists()
            seen.append(record.record_sha256)
            return committed(record)

        acked = spool.acknowledge(
            records[0].binding, expected_actual=actual(records[0]), reconcile=commit
        )
        assert acked.acknowledged and seen == [records[0].record_sha256]
        assert path(root, records[0].binding).exists()
        assert len(spool.pending(value.scope).items) == 2
        assert spool.acknowledge(
            records[0].binding, expected_actual=actual(records[0]), reconcile=committed
        ).acknowledged
        for limit in (True, 0, 101):
            with pytest.raises(SpoolConfigurationError):
                spool.pending(value.scope, limit=limit)
    with ReceiptSpool(root) as recovered:
        assert recovered.read(records[0].binding).acknowledged
        assert len(recovered.pending(value.scope).items) == 2


@pytest.mark.parametrize(
    "failure", ["callback", "unknown", "attempt", "reservation", "actual", "permit"]
)
def test_failed_native_callback_keeps_pending(tmp_path, failure):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        record = store(spool, value)

        def reconcile(data):
            receipt = committed(data)
            if failure == "callback":
                raise RuntimeError("private native diagnostic")
            if failure == "unknown":
                return replace(receipt, state="held_unknown", actual=None)
            if failure == "attempt":
                return replace(receipt, attempt_id=uuid4())
            if failure == "reservation":
                return replace(receipt, reserved=ResourceAmount(requests=1))
            if failure == "actual":
                return replace(receipt, actual=ResourceAmount(requests=1))
            return replace(receipt, dispatch_permitted=True)

        with pytest.raises(SpoolError) as error:
            spool.acknowledge(
                value, expected_actual=actual(record), reconcile=reconcile
            )
        assert "private native diagnostic" not in str(error.value)
        assert not path(root, value, "ack").exists()
        assert spool.pending(value.scope).items == (record,)


@pytest.mark.parametrize("stage", ["file_fsync", "rename", "directory_fsync"])
def test_ack_filesystem_failure_preserves_pending_exact_replay(
    tmp_path, monkeypatch, stage
):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        record = store(spool, value)
        original_fsync, original_rename = module.os.fsync, module._rename_noreplace
        failed = False

        def fail_fsync(fd):
            nonlocal failed
            directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            if not failed and (
                (stage == "file_fsync" and not directory)
                or (stage == "directory_fsync" and directory)
            ):
                failed = True
                raise OSError("private filesystem diagnostic")
            return original_fsync(fd)

        def fail_rename(*args):
            if stage == "rename":
                raise OSError("private filesystem diagnostic")
            return original_rename(*args)

        with monkeypatch.context() as changed:
            changed.setattr(module.os, "fsync", fail_fsync)
            changed.setattr(module, "_rename_noreplace", fail_rename)
            with pytest.raises(SpoolStorageError) as error:
                spool.acknowledge(
                    value, expected_actual=actual(record), reconcile=committed
                )
            assert "private filesystem diagnostic" not in str(error.value)
        assert spool.pending(value.scope).items == (record,)
        assert spool.acknowledge(
            value, expected_actual=actual(record), reconcile=committed
        ).acknowledged


def test_concurrent_writers_same_record_and_conflict(tmp_path):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as one, ReceiptSpool(root) as two:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(store, one, value), pool.submit(store, two, value)]
            records = [future.result(timeout=10) for future in futures]
        assert records[0] == records[1] and len(one.pending(value.scope).items) == 1
        with ThreadPoolExecutor(max_workers=2) as pool:
            different = pool.submit(store, one, value, observation(b"changed"))
            identical = pool.submit(store, two, value)
            with pytest.raises(SpoolConflict):
                different.result(timeout=10)
            assert identical.result(timeout=10) == records[0]


CHILD = r"""
import hashlib,json,os,signal,stat,sys
from pathlib import Path
from app import receipt_spool as m
from app.receipt_spool import ReceiptSpool,_decode_binding
from app.gemini_transport import CompleteObservation
root,manifest,marker,stage=sys.argv[1:]
binding=_decode_binding(json.loads(Path(manifest).read_text()))
raw=b'private complete response'
observation=CompleteObservation(200,raw,len(raw),10,hashlib.sha256(raw).hexdigest())
original_fsync,original_rename=m.os.fsync,m._rename_noreplace
def stop():
    Path(marker).write_text('reached')
    os.kill(os.getpid(),signal.SIGKILL)
def fsync(fd):
    regular=stat.S_ISREG(os.fstat(fd).st_mode)
    if stage=='before_file_fsync' and regular:stop()
    result=original_fsync(fd)
    if stage=='after_file_fsync' and regular:stop()
    return result
def rename(*args):
    if stage=='before_rename':stop()
    result=original_rename(*args)
    if stage=='after_rename':stop()
    return result
m.os.fsync,m._rename_noreplace=fsync,rename
with ReceiptSpool(Path(root)) as spool:
    spool.store_complete(binding,observation,outgoing_bytes=10,response_limit_bytes=2097152)
    if stage=='after_directory_fsync':stop()
"""


@pytest.mark.parametrize(
    "stage",
    [
        "before_file_fsync",
        "after_file_fsync",
        "before_rename",
        "after_rename",
        "after_directory_fsync",
    ],
)
def test_actual_sigkill_restart_has_only_complete_or_absent_record(tmp_path, stage):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root):
        pass
    manifest, marker = tmp_path / "binding.json", tmp_path / "reached"
    manifest.write_text(json.dumps(value.to_json()))
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(root), str(manifest), str(marker), stage],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == -signal.SIGKILL, result.stderr.decode()
    assert marker.read_text() == "reached"
    with ReceiptSpool(root) as restarted:
        page = restarted.pending(value.scope)
        if stage in ("after_rename", "after_directory_fsync"):
            assert (
                len(page.items) == 1
                and page.items[0].observation.raw_bytes == b"private complete response"
            )
            assert not page.items[0].acknowledged
        else:
            assert page.items == ()
            with pytest.raises(SpoolNotFound):
                restarted.read(value)
        # Republish a retained original observation, never repeat provider I/O.
        data = replace(observation(b"private complete response"), elapsed_ms=10)
        assert store(restarted, value, data).observation == data


def test_noreplace_race_cannot_overwrite_existing_object(tmp_path, monkeypatch):
    root, value = tmp_path / "spool", binding()
    original = module._rename_noreplace

    def race(directory, source, destination):
        fd = os.open(
            destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory
        )
        os.write(fd, b"adversarial existing object")
        os.close(fd)
        return original(directory, source, destination)

    with ReceiptSpool(root) as spool:
        monkeypatch.setattr(module, "_rename_noreplace", race)
        with pytest.raises(SpoolStorageError):
            store(spool, value)
        assert path(root, value).read_bytes() == b"adversarial existing object"
        with pytest.raises(SpoolCorrupt):
            spool.read(value)


def test_ack_noreplace_race_preserves_existing_marker(tmp_path, monkeypatch):
    root, value = tmp_path / "spool", binding()
    original = module._rename_noreplace
    with ReceiptSpool(root) as spool:
        record = store(spool, value)

        def race(directory, source, destination):
            fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory,
            )
            os.write(fd, b"immutable existing marker")
            os.close(fd)
            return original(directory, source, destination)

        monkeypatch.setattr(module, "_rename_noreplace", race)
        with pytest.raises(SpoolStorageError):
            spool.acknowledge(
                value, expected_actual=actual(record), reconcile=committed
            )
        assert path(root, value, "ack").read_bytes() == b"immutable existing marker"
        with pytest.raises(SpoolError):
            spool.read(value)


def test_namespace_scan_is_streamed_bounded_and_missing_entry_fails_closed(
    tmp_path, monkeypatch
):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        store(spool, value)
        monkeypatch.setattr(
            module.os, "listdir", lambda *args: pytest.fail("unbounded listdir")
        )
        assert len(spool.pending(value.scope).items) == 1
        for index in range(module.MAX_NAMESPACE_ENTRIES):
            fd = os.open(
                leaf(root, value) / f".tmp-{index:032x}",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            os.close(fd)
        with pytest.raises(SpoolCorrupt, match="bound"):
            spool.pending(value.scope)


@pytest.mark.parametrize("swap", ["scope", "root"])
def test_scope_replacement_during_write_cannot_report_success(
    tmp_path, monkeypatch, swap
):
    root, value = tmp_path / "spool", binding()
    original = module._rename_noreplace
    with ReceiptSpool(root) as spool:

        def replace_directory(*args):
            original(*args)
            location = leaf(root, value) if swap == "scope" else root
            location.rename(tmp_path / "detached")
            location.mkdir(mode=0o700)

        monkeypatch.setattr(module, "_rename_noreplace", replace_directory)
        with pytest.raises(SpoolError):
            store(spool, value)


PROCESS_STORE = r"""
import hashlib,json,sys,time
from pathlib import Path
from app.receipt_spool import ReceiptSpool,_decode_binding
from app.gemini_transport import CompleteObservation
root,manifest,ready,start=sys.argv[1:]
value=_decode_binding(json.loads(Path(manifest).read_text()))
with ReceiptSpool(Path(root)) as spool:
    Path(ready).write_text('ready')
    deadline=time.monotonic()+5
    while not Path(start).exists():
        if time.monotonic()>deadline:raise RuntimeError('barrier timeout')
        time.sleep(.01)
    raw=b'one complete observation'
    observation=CompleteObservation(200,raw,len(raw),15,hashlib.sha256(raw).hexdigest())
    result=spool.store_complete(value,observation,outgoing_bytes=10)
    print(result.record_sha256,flush=True)
"""


def test_actual_two_process_writers_publish_one_identical_record(tmp_path):
    import time

    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root):
        pass
    manifest, start = tmp_path / "binding.json", tmp_path / "start"
    manifest.write_text(json.dumps(value.to_json()))
    processes = []
    try:
        for index in range(2):
            ready = tmp_path / f"ready-{index}"
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        PROCESS_STORE,
                        str(root),
                        str(manifest),
                        str(ready),
                        str(start),
                    ],
                    cwd=Path(__file__).parents[1],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        deadline = time.monotonic() + 5
        while not all((tmp_path / f"ready-{index}").exists() for index in range(2)):
            assert time.monotonic() < deadline, "process barrier timeout"
            time.sleep(0.01)
        start.write_text("start")
        outputs = [process.communicate(timeout=10) for process in processes]
        assert all(process.returncode == 0 for process in processes), outputs
        assert outputs[0][0] == outputs[1][0]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    with ReceiptSpool(root) as recovered:
        page = recovered.pending(value.scope)
        assert (
            len(page.items) == 1
            and page.items[0].record_sha256.encode() == outputs[0][0].strip()
        )


ACK_CHILD = r"""
import json,os,signal,sys
from pathlib import Path
from app import receipt_spool as m
from app.receipt_spool import ReceiptSpool,_decode_binding
from app.budget_contract import ResourceAmount
from app.db.budget_repository import AttemptReceipt
root,manifest,marker,stage=sys.argv[1:]
value=_decode_binding(json.loads(Path(manifest).read_text()))
def stop():
    Path(marker).write_text('reached')
    os.kill(os.getpid(),signal.SIGKILL)
original=m._rename_noreplace
def rename(*args):
    if stage=='before_ack_rename':stop()
    result=original(*args)
    if stage=='after_ack_rename':stop()
    return result
m._rename_noreplace=rename
with ReceiptSpool(Path(root)) as spool:
    record=spool.read(value)
    actual=ResourceAmount(requests=1,bytes=record.outgoing_bytes+record.observation.received_bytes,tokens=20,cost_picousd=20)
    def committed_fixture(stored):
        # Fixture contract only; this filesystem test performs no native commit.
        return AttemptReceipt(value.attempt_id,'settled',value.reserved,actual,False)
    spool.acknowledge(value,expected_actual=actual,reconcile=committed_fixture)
    if stage=='after_ack_directory_fsync':stop()
"""


@pytest.mark.parametrize(
    "stage", ["before_ack_rename", "after_ack_rename", "after_ack_directory_fsync"]
)
def test_actual_sigkill_ack_restart_preserves_raw_and_commit_callback_boundary(
    tmp_path, stage
):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        before = store(spool, value)
    manifest, marker = tmp_path / "binding.json", tmp_path / "reached"
    manifest.write_text(json.dumps(value.to_json()))
    result = subprocess.run(
        [sys.executable, "-c", ACK_CHILD, str(root), str(manifest), str(marker), stage],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == -signal.SIGKILL, result.stderr.decode()
    assert marker.read_text() == "reached"
    with ReceiptSpool(root) as recovered:
        record = recovered.read(value)
        assert (
            record.observation == before.observation
            and record.record_sha256 == before.record_sha256
        )
        assert record.acknowledged == (stage != "before_ack_rename")
        assert len(recovered.pending(value.scope).items) == (
            1 if stage == "before_ack_rename" else 0
        )
        assert recovered.acknowledge(
            value, expected_actual=actual(record), reconcile=committed
        ).acknowledged


@pytest.mark.parametrize("attack", ["record_disappears", "scope_detaches", "fifo"])
def test_pending_never_turns_corruption_or_mid_read_disappearance_into_empty(
    tmp_path, monkeypatch, attack
):
    root, value = tmp_path / "spool", binding()
    with ReceiptSpool(root) as spool:
        store(spool, value)
        original = spool._record
        if attack == "fifo":
            path(root, value).unlink()
            os.mkfifo(path(root, value), 0o600)
        else:

            def changing_read(*args):
                if attack == "record_disappears":
                    path(root, value).unlink()
                    return original(*args)
                result = original(*args)
                leaf(root, value).rename(tmp_path / "detached")
                return result

            monkeypatch.setattr(spool, "_record", changing_read)
        with pytest.raises(SpoolCorrupt):
            spool.pending(value.scope)
