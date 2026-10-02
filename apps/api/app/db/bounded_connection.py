"""Native libpq handshake owns and explicitly closes its socket on every failure."""

import selectors
import time

import psycopg
from psycopg import pq, waiting
from psycopg.conninfo import make_conninfo
from psycopg.adapt import AdaptersMap


class ProbeConnection(psycopg.Connection):
    """One deadline includes dialect initialization and every probe query."""

    def __init__(self, native, *, deadline, **parameters):
        super().__init__(native, **parameters)
        self._probe_deadline = deadline

    def wait(self, gen, interval=0.1, timeout=None):
        remaining = self._probe_deadline - time.monotonic()
        if remaining <= 0:
            self.close()
            raise psycopg.OperationalError("Database probe unavailable")
        try:
            return waiting.wait(gen, self.pgconn.socket, interval=interval,
                                timeout=min(remaining, timeout) if timeout is not None else remaining)
        except BaseException:
            # No cancellation request or rollback wait on an unresponsive peer.
            # Close before an exception/traceback can retain the native socket.
            self.close()
            raise


def bounded_connection(conninfo: str = "", *, probe_deadline=None, **parameters) -> psycopg.Connection:
    """Single native attempt, with deterministic cleanup independent of GC."""
    native = None
    accepted = False
    deadline = min(time.monotonic() + 2, probe_deadline) if probe_deadline is not None else time.monotonic() + 2
    try:
        context = parameters.pop("context", None)
        row_factory = parameters.pop("row_factory", None)
        cursor_factory = parameters.pop("cursor_factory", None)
        autocommit = parameters.pop("autocommit", False)
        prepare_threshold = parameters.pop("prepare_threshold", 5)
        # Database validates the one-host configuration before the dialect calls
        # this constructor. This is not a retry or route/provider fallback.
        native = pq.PGconn.connect_start(make_conninfo(conninfo, **parameters).encode("utf-8"))
        with selectors.DefaultSelector() as selector:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or native.status == pq.ConnStatus.BAD:
                    raise psycopg.OperationalError("Database connection unavailable")
                state = native.connect_poll()
                if state == pq.PollingStatus.OK:
                    native.nonblocking = 1
                    options = {"row_factory": row_factory} if row_factory is not None else {}
                    connection = (ProbeConnection(native, deadline=probe_deadline, **options)
                                  if probe_deadline is not None else psycopg.Connection(native, **options))
                    # The pinned psycopg3.3.6 constructor needs the same copied
                    # adaptation context as Connection.connect. SQLAlchemy uses
                    # this for JSONB and native typed values.
                    if context is not None:
                        connection._adapters = AdaptersMap(context.adapters)
                    if cursor_factory is not None:
                        connection.cursor_factory = cursor_factory
                    connection.autocommit = autocommit
                    connection.prepare_threshold = prepare_threshold
                    accepted = True
                    return connection
                if state not in (pq.PollingStatus.READING, pq.PollingStatus.WRITING):
                    raise psycopg.OperationalError("Database connection unavailable")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise psycopg.OperationalError("Database connection unavailable")
                event = selectors.EVENT_READ if state == pq.PollingStatus.READING else selectors.EVENT_WRITE
                descriptor = native.socket
                selector.register(descriptor, event)
                try:
                    if not selector.select(remaining):
                        raise psycopg.OperationalError("Database connection unavailable")
                finally:
                    selector.unregister(descriptor)
    except Exception:
        raise psycopg.OperationalError("Database connection unavailable") from None
    finally:
        if native is not None and not accepted:
            native.finish()
