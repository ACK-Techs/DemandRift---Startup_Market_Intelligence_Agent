"""Bounded outbox publication and send-free durable receipt recovery."""
import json
import os
from uuid import uuid5
from sqlalchemy import select, text
from app.db import budget_models
from app.budget_contract import ResourceAmount
from app.job_delivery import WakeMessage, JobPublisher, selected_delivery
from app.gemini_receipt_recovery import GeminiReceiptRecovery
from app.receipt_spool import ReceiptSpool, ReceiptScope
from app.research_runtime import ledger, model_runtime, spool_root
from app.raw_storage import RawStorage


def read_manifest(storage, scope, identity):
    parts, name = storage._scope(*scope, identity)
    directory = storage._directory(parts)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            import stat
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or not 0 < info.st_size <= 4096:
                raise ValueError('Invalid private capture manifest')
            return json.loads(stream.read(4097))
    finally:
        os.close(directory)


def reconcile_receipts(database, message):
    scope = (message.user_id, message.project_id, message.research_id)
    account = ledger(database, *scope)
    storage = RawStorage(os.environ.get('ARTIFACT_ROOT', '/data/artifacts'))
    with database.transaction(message.user_id) as session:
        attempts = session.execute(select(budget_models.attempts).where(
            budget_models.attempts.c.user_id == message.user_id,
            budget_models.attempts.c.project_id == message.project_id,
            budget_models.attempts.c.research_id == message.research_id,
            budget_models.attempts.c.state.in_(['dispatched', 'held_unknown']))).mappings().all()
    for row in attempts:
        if row['metadata']['kind'] != 'source':
            continue
        try:
            manifest = read_manifest(storage, scope, uuid5(row['attempt_id'], 'manifest'))
            if manifest.get('size', 0):
                storage.read(*scope, row['attempt_id'], manifest['digest'], manifest['size'])
            amount = ResourceAmount(requests=1, pages=1, bytes=manifest['wire_bytes'], records=manifest['records'])
            account.settle(row['attempt_id'], amount, {'receipt_version':'source-capture-v1', 'response_sha256':manifest['digest']})
        except (ValueError, OSError, RuntimeError, KeyError):
            # Missing/partial observations remain charged as unresolved holds.
            continue
    with ReceiptSpool(spool_root()) as spool:
        gateway = model_runtime(database, *scope, spool)
        recovery = GeminiReceiptRecovery(gateway.dispatcher, gateway.ledger, gateway.policy, spool)
        after = None
        while True:
            page = spool.pending(ReceiptScope(*scope), limit=50, after_attempt_id=after)
            for record in page.items:
                try:
                    recovery.reconcile(record.binding)
                except RuntimeError:
                    continue
            if page.next_after_attempt_id is None:
                break
            after = page.next_after_attempt_id


def scope_from(message):
    return (message.user_id,message.project_id,message.research_id)


class RuntimeDelivery:
    def __init__(self, database, application):
        self.database, self.publisher = database, JobPublisher(database, application)
        self.last_retention=0

    def tick(self):
        import time
        if time.monotonic()-self.last_retention>=3600:
            self.last_retention=time.monotonic()
            try:
                from app.runtime_retention import cleanup
                from app.runtime_observability import record
                removed=cleanup(os.environ.get('ARTIFACT_ROOT','/data/artifacts'))
                if removed: record('retention',status='scratch_removed',checkpoint=removed)
            except (OSError,ValueError): pass
        # Definer returns scoped identifiers only. Full data remains owner RLS.
        with self.database.transaction() as session:
            messages = [WakeMessage.model_validate(dict(row)) for row in session.execute(text('SELECT * FROM public.demandrift_pending_wakes()')).mappings()]
        for message in messages:
            try:
                reconcile_receipts(self.database, message)
                repository, _, _ = selected_delivery(self.database, message)
                recovered = repository.recover(message.research_id, message.job_id)
                from app.runtime_observability import record
                record('recovery', user_id=message.user_id, project_id=message.project_id,
                    research_id=message.research_id, job_id=message.job_id, status=recovered.job.state,
                    attempts=recovered.job.attempts, checkpoint=recovered.job.checkpoint)
                if recovered.job.state in ('failed', 'held_unknown'):
                    from app.contracts import ResearchRun, ApiError
                    from datetime import datetime, timezone
                    from app.research_runtime import current_usage
                    with repository.transaction(message.research_id) as writer:
                        run=repository.get(message.research_id,'run',message.research_id)
                        pins=repository.selections(message.research_id,'run',message.research_id)['record']
                        state='failed' if recovered.job.state=='failed' else 'partial'
                        if run.status!=state:
                            payload=run.model_dump(mode='json')
                            payload.update(status=state,usage=current_usage(self.database,*scope_from(message)).model_dump(mode='json'))
                            if state=='failed': payload['finished_at']=datetime.now(timezone.utc).isoformat()
                            payload['errors'].append(ApiError(code='worker_'+recovered.job.state,
                                message='Research stopped after finite recovery attempts.' if state=='failed' else 'Provider accounting is unresolved; further requests are held.',
                                request_id=message.job_id,stage='runtime').model_dump(mode='json'))
                            writer.put_run(ResearchRun.model_validate(payload),bundle_version=pins['bundle_version'],report_version=pins['report_version'])
                if recovered.job.state not in ('queued', 'retry_wait'):
                    continue
                pending = repository.pending_deliveries(message.research_id, message.job_id)
                for identity in pending:
                    self.publisher.publish(message.model_copy(update={'delivery_id': identity}))
                if not pending:
                    self.publisher.redrive_sent(message)
            except (ValueError, OSError, RuntimeError):
                # Dependency pulse still runs; no payload or secret in logs.
                continue
