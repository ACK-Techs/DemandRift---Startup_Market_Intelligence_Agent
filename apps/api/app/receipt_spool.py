"""Private durable complete observations; no provider send or ledger authority."""

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass, field
import errno
import fcntl
import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
from types import MappingProxyType
from uuid import UUID, uuid4

from app.budget_contract import MAX_COUNTER, ResourceAmount
from app.db.budget_repository import AttemptReceipt
from app.gemini_codec import MAX_REQUEST_BYTES
from app.gemini_contract import MODEL_ID
from app.gemini_transport import CompleteObservation
from app.job_budget_contract import AdmissionContext, context_value

MAX_RESPONSE_BYTES = 2097152
MAX_ENVELOPE_BYTES = 16384
MAX_RECORD_BYTES = MAX_RESPONSE_BYTES + MAX_ENVELOPE_BYTES
MAX_NAMESPACE_ENTRIES = 4096
MAGIC = b"DEMANDRIFT-RECEIPT-V1\n"
LOCK_SECONDS = 5
VERSION = "receipt-spool-v1"
BINDING_VERSION = "receipt-binding-v1"
META_FIELDS = {
    "kind",
    "operation_version",
    "provider",
    "model",
    "prompt_version",
    "schema_version",
    "pricing_version",
}
UUID_NAME = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class SpoolError(RuntimeError):
    """Safe diagnostics never expose root paths, observations or credentials."""


class SpoolConfigurationError(SpoolError):
    pass


class SpoolConflict(SpoolError):
    pass


class SpoolCorrupt(SpoolError):
    pass


class SpoolNotFound(SpoolError):
    pass


class SpoolStorageError(SpoolError):
    pass


def _uuid(value):
    if type(value) is not UUID:
        raise SpoolConfigurationError("Resolved server UUID required")
    return value


def _counter(value, maximum=MAX_COUNTER, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise SpoolConfigurationError("Bounded receipt counter required")
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SpoolConfigurationError("Exact receipt fingerprint required")
    return value


def _amount(value):
    if type(value) is not ResourceAmount:
        raise SpoolConfigurationError("Known native resource amount required")
    try:
        copied = ResourceAmount.from_json(value.to_json())
        if copied.requests != 1:
            raise ValueError
        return copied
    except ValueError:
        raise SpoolConfigurationError("One bounded request amount required") from None


@dataclass(frozen=True, slots=True)
class ReceiptScope:
    user_id: UUID
    project_id: UUID
    research_id: UUID

    def __post_init__(self):
        for value in (self.user_id, self.project_id, self.research_id):
            _uuid(value)

    def to_json(self):
        return {
            name: str(getattr(self, name))
            for name in ("user_id", "project_id", "research_id")
        }


@dataclass(frozen=True, slots=True)
class ReceiptBinding:
    scope: ReceiptScope
    attempt_id: UUID
    context: AdmissionContext
    input_fingerprint: str
    reserved: ResourceAmount
    metadata: object = field(repr=False)

    def __post_init__(self):
        if type(self.scope) is not ReceiptScope:
            raise SpoolConfigurationError("Resolved receipt scope required")
        object.__setattr__(
            self,
            "scope",
            ReceiptScope(
                self.scope.user_id, self.scope.project_id, self.scope.research_id
            ),
        )
        _uuid(self.attempt_id)
        _hash(self.input_fingerprint)
        try:
            object.__setattr__(self, "context", context_value(self.context))
            object.__setattr__(self, "reserved", _amount(self.reserved))
            if type(self.metadata) not in (dict, MappingProxyType):
                raise ValueError
            copied = dict(self.metadata)
            if (
                set(copied) != META_FIELDS
                or copied["kind"] != "model"
                or copied["provider"] not in ("developer", "vertex_express")
                or copied["model"] != MODEL_ID
            ):
                raise ValueError
            if any(
                type(v) is not str
                or re.fullmatch(r"[A-Za-z0-9._:/+=-]{1,256}", v) is None
                for v in copied.values()
            ):
                raise ValueError
            object.__setattr__(self, "metadata", MappingProxyType(copied))
        except (ValueError, TypeError):
            raise SpoolConfigurationError(
                "Exact immutable receipt binding required"
            ) from None

    def to_json(self):
        return {
            "binding_version": BINDING_VERSION,
            "scope": self.scope.to_json(),
            "attempt_id": str(self.attempt_id),
            "context": self.context.to_json(),
            "input_fingerprint": self.input_fingerprint,
            "reserved": self.reserved.to_json(),
            "metadata": dict(self.metadata),
        }


def _binding(value):
    if type(value) is not ReceiptBinding:
        raise SpoolConfigurationError("Resolved immutable receipt binding required")
    return ReceiptBinding(
        value.scope,
        value.attempt_id,
        value.context,
        value.input_fingerprint,
        value.reserved,
        value.metadata,
    )


def _decode_binding(value):
    if (
        set(value)
        != {
            "binding_version",
            "scope",
            "attempt_id",
            "context",
            "input_fingerprint",
            "reserved",
            "metadata",
        }
        or value["binding_version"] != BINDING_VERSION
    ):
        raise ValueError
    scope = value["scope"]
    if set(scope) != {"user_id", "project_id", "research_id"}:
        raise ValueError
    context = value["context"]
    if set(context) != {
        "mode",
        "brief_id",
        "brief_version",
        "job_id",
        "lease_owner",
        "fence",
    }:
        raise ValueError
    return ReceiptBinding(
        ReceiptScope(
            *(UUID(scope[k]) for k in ("user_id", "project_id", "research_id"))
        ),
        UUID(value["attempt_id"]),
        AdmissionContext(
            context["mode"],
            UUID(context["brief_id"]),
            context["brief_version"],
            UUID(context["job_id"]) if context["job_id"] is not None else None,
            UUID(context["lease_owner"])
            if context["lease_owner"] is not None
            else None,
            context["fence"],
        ),
        value["input_fingerprint"],
        ResourceAmount.from_json(value["reserved"]),
        value["metadata"],
    )


@dataclass(frozen=True, slots=True)
class SpoolRecord:
    binding: ReceiptBinding
    operation: str
    outgoing_bytes: int
    response_limit_bytes: int
    observation: CompleteObservation = field(repr=False)
    record_sha256: str
    acknowledged: bool = False


@dataclass(frozen=True, slots=True)
class PendingPage:
    items: tuple[SpoolRecord, ...]
    next_after_attempt_id: UUID | None


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
    )
    if _canonical(value) != raw:
        raise ValueError
    return value


def _encode(binding, observation, operation, outgoing, limit):
    if (
        type(observation) is not CompleteObservation
        or type(observation.raw_bytes) is not bytes
    ):
        raise SpoolConfigurationError("Complete bounded observation required")
    _counter(limit, MAX_RESPONSE_BYTES, 1024)
    _counter(outgoing, MAX_REQUEST_BYTES, 1)
    _counter(observation.status_code, 599, 100)
    _counter(observation.received_bytes, limit)
    _counter(observation.elapsed_ms)
    _hash(observation.response_sha256)
    if operation not in ("generate", "count") or type(operation) is not str:
        raise SpoolConfigurationError("Fixed model operation required")
    if (
        len(observation.raw_bytes) != observation.received_bytes
        or hashlib.sha256(observation.raw_bytes).hexdigest()
        != observation.response_sha256
    ):
        raise SpoolConfigurationError("Observation bytes or hash differ")
    envelope = _canonical(
        {
            "format_version": VERSION,
            "binding": binding.to_json(),
            "operation": operation,
            "outgoing_bytes": outgoing,
            "response_limit_bytes": limit,
            "observation": {
                "status_code": observation.status_code,
                "received_bytes": observation.received_bytes,
                "elapsed_ms": observation.elapsed_ms,
                "response_sha256": observation.response_sha256,
            },
        }
    )
    prefix = MAGIC + struct.pack(">I", len(envelope))
    if len(prefix) + len(envelope) > MAX_ENVELOPE_BYTES:
        raise SpoolConfigurationError("Receipt envelope exceeds its bound")
    return prefix + envelope + observation.raw_bytes


def _decode(raw):
    try:
        if not raw.startswith(MAGIC) or len(raw) < len(MAGIC) + 4:
            raise ValueError
        size = struct.unpack(">I", raw[len(MAGIC) : len(MAGIC) + 4])[0]
        start = len(MAGIC) + 4
        if size + start > MAX_ENVELOPE_BYTES or size + start > len(raw):
            raise ValueError
        envelope = _json(raw[start : start + size])
        if (
            set(envelope)
            != {
                "format_version",
                "binding",
                "operation",
                "outgoing_bytes",
                "response_limit_bytes",
                "observation",
            }
            or envelope["format_version"] != VERSION
        ):
            raise ValueError
        data = envelope["observation"]
        if set(data) != {
            "status_code",
            "received_bytes",
            "elapsed_ms",
            "response_sha256",
        }:
            raise ValueError
        binding = _decode_binding(envelope["binding"])
        observation = CompleteObservation(
            data["status_code"],
            raw[start + size :],
            data["received_bytes"],
            data["elapsed_ms"],
            data["response_sha256"],
        )
        if (
            _encode(
                binding,
                observation,
                envelope["operation"],
                envelope["outgoing_bytes"],
                envelope["response_limit_bytes"],
            )
            != raw
        ):
            raise ValueError
        return SpoolRecord(
            binding,
            envelope["operation"],
            envelope["outgoing_bytes"],
            envelope["response_limit_bytes"],
            observation,
            hashlib.sha256(raw).hexdigest(),
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
        SpoolError,
        struct.error,
    ):
        raise SpoolCorrupt("Invalid durable receipt") from None


def _rename_noreplace(directory, source, destination):
    """Atomic no-overwrite publication on the supported Linux/macOS hosts."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function, flag = getattr(libc, "renameatx_np", None), 4  # SDK RENAME_EXCL
    elif sys.platform.startswith("linux"):
        function, flag = getattr(libc, "renameat2", None), 1  # RENAME_NOREPLACE
    else:
        function, flag = None, 0
    if function is None:
        raise SpoolConfigurationError("Atomic no-overwrite filesystem support required")
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    if (
        function(
            directory,
            source.encode("ascii"),
            directory,
            destination.encode("ascii"),
            flag,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise OSError(error, "Atomic receipt publication failed")


def _private(info, directory=False):
    wanted = 0o700 if directory else 0o600
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (
        not valid
        or stat.S_IMODE(info.st_mode) != wanted
        or info.st_uid != os.geteuid()
        or (not directory and info.st_nlink != 1)
    ):
        raise SpoolCorrupt("Private receipt storage policy differs")


def _directory(parent, name):
    fd = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent
    )
    try:
        info = os.fstat(fd)
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino):
            raise SpoolCorrupt("Private receipt directory changed")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_file(directory, name, maximum):
    fd = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        dir_fd=directory,
    )
    try:
        before = os.fstat(fd)
        _private(before)
        if before.st_size > maximum:
            raise SpoolCorrupt("Durable receipt exceeds its bound")
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        _private(after)
        _private(named)
        if (
            len(raw) != before.st_size
            or len(raw) > maximum
            or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
            or (after.st_dev, after.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise SpoolCorrupt("Durable receipt changed during read")
        return bytes(raw)
    finally:
        os.close(fd)


class ReceiptSpool:
    def __init__(self, root):
        self._fd = None
        try:
            self._root = Path(root)
            if (
                not self._root.is_absolute()
                or ".." in self._root.parts
                or self._root == Path("/")
            ):
                raise SpoolConfigurationError(
                    "Canonical absolute private root required"
                )
            self._fd = self._open_root(create=True)
            _private(os.fstat(self._fd), directory=True)
        except (OSError, ValueError, TypeError, SpoolError):
            self.close()
            raise SpoolConfigurationError(
                "Private receipt root is unavailable"
            ) from None

    def __repr__(self):
        return "ReceiptSpool()"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def _open_root(self, create=False):
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for index, name in enumerate(self._root.parts[1:]):
                try:
                    child = _directory(fd, name)
                except FileNotFoundError:
                    if not create or index != len(self._root.parts) - 2:
                        raise
                    try:
                        os.mkdir(name, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    os.fsync(fd)
                    child = _directory(fd, name)
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise

    @contextmanager
    def _scope(self, scope, create=False):
        if self._fd is None or type(scope) is not ReceiptScope:
            raise SpoolConfigurationError("Open private receipt scope required")
        scope = ReceiptScope(scope.user_id, scope.project_id, scope.research_id)
        try:
            check = self._open_root()
        except OSError:
            raise SpoolCorrupt("Private receipt root changed") from None
        try:
            if (os.fstat(check).st_dev, os.fstat(check).st_ino) != (
                os.fstat(self._fd).st_dev,
                os.fstat(self._fd).st_ino,
            ):
                raise SpoolCorrupt("Private receipt root changed")
            _private(os.fstat(check), directory=True)
        finally:
            os.close(check)
        descriptors = [os.dup(self._fd)]
        names = tuple(scope.to_json().values())
        try:
            for name in names:
                fd = descriptors[-1]
                if create:
                    try:
                        os.mkdir(name, 0o700, dir_fd=fd)
                        os.fsync(fd)
                    except FileExistsError:
                        pass
                child = _directory(fd, name)
                try:
                    _private(os.fstat(child), directory=True)
                except BaseException:
                    os.close(child)
                    raise
                descriptors.append(child)
            yield descriptors[-1]
            # Do not report success if a same-identity filesystem mutation
            # detached the pinned scope while I/O was in progress.
            try:
                for parent, child, name in zip(descriptors, descriptors[1:], names):
                    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    opened = os.fstat(child)
                    _private(named, directory=True)
                    _private(opened, directory=True)
                    if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
                        raise SpoolCorrupt("Private receipt scope changed")
                check = self._open_root()
                try:
                    _private(os.fstat(check), directory=True)
                    if (os.fstat(check).st_dev, os.fstat(check).st_ino) != (
                        os.fstat(self._fd).st_dev,
                        os.fstat(self._fd).st_ino,
                    ):
                        raise SpoolCorrupt("Private receipt root changed")
                finally:
                    os.close(check)
            except OSError:
                raise SpoolCorrupt("Private receipt scope changed") from None
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    @contextmanager
    def _lock(self, directory, attempt):
        name = f".{attempt}.lock"
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        try:
            fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        except FileExistsError:
            fd = os.open(name, flags, dir_fd=directory)
        try:
            _private(os.fstat(fd))
            if os.fstat(fd).st_size:
                raise SpoolCorrupt("Invalid receipt lock")
            deadline = time.monotonic() + LOCK_SECONDS
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise SpoolStorageError("Receipt lock is unavailable") from None
                    time.sleep(0.01)
            named = os.stat(name, dir_fd=directory, follow_symlinks=False)
            _private(named)
            _private(os.fstat(fd))
            if (named.st_dev, named.st_ino) != (
                os.fstat(fd).st_dev,
                os.fstat(fd).st_ino,
            ):
                raise SpoolCorrupt("Private receipt lock changed")
            yield
        finally:
            os.close(fd)

    @staticmethod
    def _publish(directory, name, raw, *, rollback_after_rename=False):
        temporary = f".tmp-{uuid4().hex}"
        fd = None
        published = False
        try:
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=directory,
            )
            _private(os.fstat(fd))
            view = memoryview(raw)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise OSError(errno.EIO, "Receipt write failed")
                view = view[count:]
            os.fsync(fd)
            published_info = os.fstat(fd)
            os.close(fd)
            fd = None
            _rename_noreplace(directory, temporary, name)
            published = True
            try:
                os.fsync(directory)
            except OSError:
                if rollback_after_rename:
                    named = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    _private(named)
                    if (named.st_dev, named.st_ino) != (
                        published_info.st_dev,
                        published_info.st_ino,
                    ):
                        raise SpoolCorrupt("Private acknowledgement changed") from None
                    os.unlink(name, dir_fd=directory)
                    os.fsync(directory)
                raise
        finally:
            if fd is not None:
                os.close(fd)
            if not published:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _record(directory, attempt, expected=None):
        record = _decode(_read_file(directory, f"{attempt}.receipt", MAX_RECORD_BYTES))
        if record.binding.attempt_id != attempt or (
            expected is not None and record.binding != expected
        ):
            raise SpoolConflict("Durable receipt binding differs")
        try:
            ack = _json(_read_file(directory, f"{attempt}.ack", MAX_ENVELOPE_BYTES))
        except FileNotFoundError:
            return record
        if (
            set(ack) != {"format_version", "record_sha256", "binding", "settlement"}
            or ack["format_version"] != VERSION
            or ack["record_sha256"] != record.record_sha256
            or ack["binding"] != record.binding.to_json()
        ):
            raise SpoolCorrupt("Invalid durable acknowledgement")
        if (
            set(ack["settlement"])
            != {"attempt_id", "state", "reserved", "actual", "dispatch_permitted"}
            or ack["settlement"]["attempt_id"] != str(attempt)
            or ack["settlement"]["dispatch_permitted"] is not False
        ):
            raise SpoolCorrupt("Invalid durable acknowledgement")
        ReceiptSpool._validate_settlement(
            record,
            AttemptReceipt.parse(ack["settlement"]),
            ResourceAmount.from_json(ack["settlement"]["actual"]),
        )
        return SpoolRecord(
            record.binding,
            record.operation,
            record.outgoing_bytes,
            record.response_limit_bytes,
            record.observation,
            record.record_sha256,
            True,
        )

    def store_complete(
        self,
        binding,
        observation,
        *,
        operation="generate",
        outgoing_bytes,
        response_limit_bytes=MAX_RESPONSE_BYTES,
    ):
        binding = _binding(binding)
        raw = _encode(
            binding, observation, operation, outgoing_bytes, response_limit_bytes
        )
        try:
            with (
                self._scope(binding.scope, create=True) as directory,
                self._lock(directory, binding.attempt_id),
            ):
                try:
                    old = _read_file(
                        directory, f"{binding.attempt_id}.receipt", MAX_RECORD_BYTES
                    )
                except FileNotFoundError:
                    self._publish(directory, f"{binding.attempt_id}.receipt", raw)
                else:
                    _decode(old)
                    if old != raw:
                        raise SpoolConflict("Immutable observation differs")
                    # Also confirms durability after a lost post-rename reply.
                    fd = os.open(
                        f"{binding.attempt_id}.receipt",
                        os.O_RDONLY | os.O_NOFOLLOW,
                        dir_fd=directory,
                    )
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    os.fsync(directory)
                return self._record(directory, binding.attempt_id, binding)
        except SpoolError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
        ):
            raise SpoolStorageError("Durable receipt storage is unavailable") from None

    def read(self, binding):
        binding = _binding(binding)
        try:
            with self._scope(binding.scope) as directory:
                return self._record(directory, binding.attempt_id, binding)
        except FileNotFoundError:
            raise SpoolNotFound("Durable receipt not found") from None
        except SpoolError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
        ):
            raise SpoolCorrupt("Durable receipt is unavailable") from None

    def pending(self, scope, *, limit=50, after_attempt_id=None):
        _counter(limit, 100, 1)
        if after_attempt_id is not None:
            _uuid(after_attempt_id)
        try:
            with self._scope(scope) as directory:
                try:
                    # scandir streams names; the heap retains at most limit+1
                    # complete records, independent of namespace size.
                    selected = []
                    with os.scandir(directory) as entries:
                        for count, entry in enumerate(entries, 1):
                            if count > MAX_NAMESPACE_ENTRIES:
                                raise SpoolCorrupt(
                                    "Private receipt namespace exceeds its bound"
                                )
                            name = entry.name
                            info = os.stat(
                                name, dir_fd=directory, follow_symlinks=False
                            )
                            _private(info)
                            if info.st_size > MAX_RECORD_BYTES:
                                raise SpoolCorrupt(
                                    "Private receipt entry exceeds its bound"
                                )
                            if re.fullmatch(UUID_NAME + r"\.receipt", name):
                                attempt = UUID(name[:-8])
                                record = self._record(directory, attempt)
                                if record.binding.scope != scope:
                                    raise SpoolCorrupt("Private receipt scope differs")
                                if record.acknowledged or (
                                    after_attempt_id is not None
                                    and attempt <= after_attempt_id
                                ):
                                    continue
                                heapq.heappush(selected, (-attempt.int, record))
                                if len(selected) > limit + 1:
                                    heapq.heappop(selected)
                            elif re.fullmatch(UUID_NAME + r"\.ack", name):
                                try:
                                    _private(
                                        os.stat(
                                            name[:-4] + ".receipt",
                                            dir_fd=directory,
                                            follow_symlinks=False,
                                        )
                                    )
                                except FileNotFoundError:
                                    raise SpoolCorrupt(
                                        "Orphan durable acknowledgement"
                                    ) from None
                            elif re.fullmatch(r"\." + UUID_NAME + r"\.lock", name):
                                if info.st_size:
                                    raise SpoolCorrupt("Invalid receipt lock")
                            elif not re.fullmatch(r"\.tmp-[0-9a-f]{32}", name):
                                raise SpoolCorrupt("Unexpected private receipt entry")
                    items = sorted(
                        (record for _, record in selected),
                        key=lambda record: record.binding.attempt_id,
                    )
                    if len(items) > limit:
                        return PendingPage(
                            tuple(items[:limit]), items[limit - 1].binding.attempt_id
                        )
                    return PendingPage(tuple(items), None)
                except FileNotFoundError:
                    raise SpoolCorrupt("Private receipt namespace changed") from None
        except FileNotFoundError:
            return PendingPage((), None)
        except SpoolError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
        ):
            raise SpoolCorrupt("Durable receipt enumeration is unavailable") from None

    @staticmethod
    def _validate_settlement(record, receipt, expected):
        expected = _amount(expected)
        if (
            type(receipt) is not AttemptReceipt
            or receipt.attempt_id != record.binding.attempt_id
            or receipt.reserved != record.binding.reserved
            or receipt.actual != expected
            or receipt.state not in ("settled", "overrun")
            or receipt.dispatch_permitted is not False
            or expected.bytes
            != record.outgoing_bytes + record.observation.received_bytes
        ):
            raise SpoolConflict("Known committed settlement differs")
        if (receipt.state == "overrun") != (not expected.fits(record.binding.reserved)):
            raise SpoolConflict("Known settlement state differs")

    def acknowledge(self, binding, *, expected_actual, reconcile):
        binding = _binding(binding)
        expected_actual = _amount(expected_actual)
        if not callable(reconcile):
            raise SpoolConfigurationError(
                "Trusted native reconciliation callback required"
            )
        try:
            with (
                self._scope(binding.scope) as directory,
                self._lock(directory, binding.attempt_id),
            ):
                record = self._record(directory, binding.attempt_id, binding)
                try:
                    committed = reconcile(record)
                except Exception:
                    raise SpoolStorageError(
                        "Committed native accounting is unavailable"
                    ) from None
                self._validate_settlement(record, committed, expected_actual)
                settlement = {
                    "attempt_id": str(committed.attempt_id),
                    "state": committed.state,
                    "reserved": binding.reserved.to_json(),
                    "actual": expected_actual.to_json(),
                    "dispatch_permitted": False,
                }
                ack = _canonical(
                    {
                        "format_version": VERSION,
                        "record_sha256": record.record_sha256,
                        "binding": binding.to_json(),
                        "settlement": settlement,
                    }
                )
                if len(ack) > MAX_ENVELOPE_BYTES:
                    raise SpoolConflict("Acknowledgement exceeds its bound")
                name = f"{binding.attempt_id}.ack"
                try:
                    old = _read_file(directory, name, MAX_ENVELOPE_BYTES)
                except FileNotFoundError:
                    # Roll back only our own newly renamed marker after an
                    # unconfirmed directory fsync, never an existing marker.
                    self._publish(directory, name, ack, rollback_after_rename=True)
                else:
                    if old != ack:
                        raise SpoolConflict("Immutable acknowledgement differs")
                    os.fsync(directory)
                return self._record(directory, binding.attempt_id, binding)
        except SpoolError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
        ):
            raise SpoolStorageError("Durable acknowledgement is unavailable") from None
