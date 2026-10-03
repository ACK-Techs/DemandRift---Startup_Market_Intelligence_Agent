"""Production worker startup with restricted database and expiring dependency pulse."""

import os
import threading
from uuid import uuid4

from celery.signals import worker_process_init, worker_ready, worker_shutdown

from app.db.engine import Database
from app.runtime_health import database_ready, publish_worker_pulse, queue_connection
from app.runtime_secrets import runtime_secret
from app.worker_app import make_worker_app
from app.worker_config import WorkerSettings
from app.research_pipeline import pipeline
from app.runtime_delivery import RuntimeDelivery


class RuntimeWorkerUnavailable(RuntimeError):
    pass


def configured_application():
    database = connection = None
    try:
        settings = WorkerSettings.from_environment()
        database = Database(runtime_secret("DATABASE_URL", allow_environment=False), pool_size=2)
        database.assert_application_role()
        if not database_ready(database):
            raise ValueError()
        connection = queue_connection(settings)
        if connection.ping() is not True:
            raise ValueError()
        application = make_worker_app(settings, database=database, handler=pipeline)
    except Exception:
        if connection is not None:
            connection.close()
        if database is not None:
            database.close()
        raise RuntimeWorkerUnavailable("Worker runtime dependencies unavailable") from None

    stop = threading.Event()
    thread = None
    instance = str(uuid4())
    revision = os.environ.get("APP_REVISION", "development")

    delivery = RuntimeDelivery(database, application)

    def beat():
        while not stop.is_set():
            try:
                publish_worker_pulse(connection, database, revision, instance,
                                     key=settings.key_prefix + "runtime:worker")
                delivery.tick()
            except Exception:
                # An unavailable dependency expires the prior pulse without secret diagnostics.
                pass
            stop.wait(10)

    def on_ready(sender=None, **kwargs):
        nonlocal thread
        if getattr(sender, "app", None) is application and thread is None:
            thread = threading.Thread(target=beat, name="demandrift-runtime-pulse", daemon=True)
            thread.start()

    def on_process_init(sender=None, **kwargs):
        # Child processes must never reuse connections opened before fork.
        database.engine.dispose(close=False)
        connection.connection_pool.reset()

    def on_shutdown(sender=None, **kwargs):
        if getattr(sender, "app", None) is not application:
            return
        stop.set()
        if thread is not None:
            thread.join(timeout=15)
        connection.close()
        database.close()

    worker_ready.connect(on_ready, weak=False)
    worker_process_init.connect(on_process_init, weak=False)
    worker_shutdown.connect(on_shutdown, weak=False)
    return application


app = configured_application()
