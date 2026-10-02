"""Native outbox publication and explicit scoped recovery of lost queue wakes."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.db import job_models as tables
from app.db.job_repository import JobRepository
from app.db.preparation_repository import RecordNotFound
from app.job_contract import LeaseToken
from app.worker_config import TASK_NAME


class WakeMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    project_id: UUID
    research_id: UUID
    job_id: UUID
    delivery_id: UUID

    def repository(self, database):
        return JobRepository(database, self.user_id, self.project_id)


def selected_delivery(database, message):
    repo = message.repository(database)
    if repo.get_project().archived_at is not None:
        raise RecordNotFound("Active project required")
    job = repo.get_job(message.research_id, message.job_id)
    with database.transaction(message.user_id) as session:
        row = (
            session.execute(
                select(tables.outbox).where(
                    tables.outbox.c.user_id == message.user_id,
                    tables.outbox.c.project_id == message.project_id,
                    tables.outbox.c.research_id == message.research_id,
                    tables.outbox.c.job_id == message.job_id,
                    tables.outbox.c.delivery_id == message.delivery_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RecordNotFound("Delivery not found")
        return repo, job, dict(row)


class JobPublisher:
    def __init__(self, database, application):
        self.database, self.application = database, application

    def _send(self, message):
        # Bind this publication explicitly to this application's Redis
        # connection and queue namespace.
        with self.application.connection_for_write() as connection:
            self.application.send_task(
                TASK_NAME,
                kwargs={"payload": message.model_dump(mode="json")},
                task_id=str(message.delivery_id),
                queue=self.application.conf.task_default_queue,
                serializer="json",
                retry=False,
                ignore_result=True,
                connection=connection,
            )

    def publish(self, message):
        message = WakeMessage.model_validate(message)
        if getattr(self.application, "pipeline_handler", None) is None:
            return "handler_unavailable"
        repo, _, _ = selected_delivery(self.database, message)
        receipt = repo.claim_delivery(
            message.research_id,
            message.job_id,
            message.delivery_id,
            uuid4(),
            lease_seconds=self.application.worker_settings.lease_seconds,
        )
        if not receipt.publish_permitted:
            return "not_permitted"
        # No acknowledgement on a publish exception, including an ambiguous
        # broker outcome. Expiry and bounded native reclaim own the next attempt.
        self._send(message)
        acknowledged = repo.acknowledge_delivery(
            message.research_id,
            message.job_id,
            message.delivery_id,
            LeaseToken(owner=receipt.lease_owner, fence=receipt.fence),
        )
        return "published" if acknowledged.state == "sent" else "not_permitted"

    def redrive_sent(self, message):
        """One explicit transport redrive; never a provider-effect replay."""
        message = WakeMessage.model_validate(message)
        if getattr(self.application, "pipeline_handler", None) is None:
            return "handler_unavailable"
        _, job, row = selected_delivery(self.database, message)
        if row["state"] != "sent" or job.state not in ("queued", "retry_wait"):
            return "not_permitted"
        self._send(message)
        return "redriven"
