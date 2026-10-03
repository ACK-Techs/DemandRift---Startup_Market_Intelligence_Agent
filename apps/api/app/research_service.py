"""Transactional start, scoped read models and recovery for the durable pipeline."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4, uuid5, UUID
from sqlalchemy import select, text, tuple_, update
from app import contracts as c
from app.db import evidence_models as evidence, job_models as jobs
from app.db.evidence_repository import EvidenceWriter
from app.db.job_repository import JobRepository, JobConflict
from app.db.phase1_repository import Phase1Repository
from app.db.preparation_repository import RecordNotFound
from app.research_runtime import ledger, validate_budget
from app.budget_contract import BudgetCapacity
from app.job_contract import JobReceipt


class ResearchService(JobRepository):
    def start(self, research, key, body):
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            self._research(session, research, lock=True)
            old = session.execute(select(jobs.jobs).where(*self._where(jobs.jobs, research))).mappings().one_or_none()
            if old is not None:
                if old['request_fingerprint'] != fingerprint:
                    raise JobConflict('Start input differs from existing research')
                self._validate_binding(session, research, old)
                return self._get(session, research, 'run', research)
            foreign = session.execute(select(jobs.jobs.c.research_id).where(jobs.jobs.c.user_id == self.user_id,
                jobs.jobs.c.project_id == self.project_id, jobs.jobs.c.request_key == key)).scalar_one_or_none()
            if foreign:
                raise JobConflict('Operation key already belongs to another research')
            plan = self._plan(session, research, body.expected_plan_id, body.expected_plan_version)
            if plan.plan_fingerprint != body.expected_plan_fingerprint or plan.status != 'confirmed':
                raise JobConflict('Exact approved plan required')
            if (plan.brief_id, plan.brief_version) != (body.expected_brief_id, body.expected_brief_version):
                raise JobConflict('Start brief differs from approved plan')
            phase1 = Phase1Repository(self.database, self.user_id, self.project_id)
            eligibility = phase1._eligibility(session, plan)
            if not eligibility.can_start:
                raise JobConflict('Current plan is not eligible for research start')
            now = datetime.now(timezone.utc)
            base = dict(user_id=self.user_id, project_id=self.project_id, research_id=research,
                created_at=now, versions=plan.versions)
            executions = [c.QueryExecution(**base, execution_id=uuid4(), query_id=query.query_id,
                source_id=query.source_id, attempt=1, status='queued', counts=c.SourceCounts(), usage=c.Usage()) for query in plan.query_plan]
            run = c.ResearchRun(**base, status='queued', phase='planning', brief_id=plan.brief_id,
                brief_version=plan.brief_version, research_plan_id=plan.research_plan_id, plan_version=plan.plan_version,
                plan_fingerprint=plan.plan_fingerprint, budget=plan.budget, usage=c.Usage(), cancel_requested=False,
                source_executions=executions)
            writer = EvidenceWriter(self, session, research)
            writer.put_run(run)
            session.execute(jobs.jobs.insert().values(user_id=self.user_id, project_id=self.project_id, research_id=research,
                job_id=uuid4(), request_key=key, request_fingerprint=fingerprint,
                research_plan_id=plan.research_plan_id, plan_version=plan.plan_version, plan_fingerprint=plan.plan_fingerprint,
                brief_id=plan.brief_id, brief_version=plan.brief_version, max_attempts=3))
            writer.flush_associations()
            writer.seal()
            return run

    def rows(self, research, kind, *, limit=25, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Bounded page required')
        from app.db.evidence_repository import SPECS
        table = evidence.TABLES[kind]
        _, identity, version = SPECS[kind]
        after = None
        if cursor is not None:
            import base64
            try:
                data = json.loads(base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True))
                if type(data) is not list or len(data) != 7 or data[:4] != [str(self.user_id), str(self.project_id), str(research), kind]:
                    raise ValueError()
                stamp = datetime.fromisoformat(data[4])
                if stamp.tzinfo is None or type(data[6]) is not int or data[6] < 1:
                    raise ValueError()
                after = (stamp, UUID(data[5]), data[6])
            except (ValueError, TypeError, IndexError):
                raise ValueError('Invalid page cursor') from None
        with self.database.transaction(self.user_id) as session:
            self._project(session)
            self._research(session, research)
            ordering = [table.c.created_at, table.c[identity], *([table.c[version]] if version else [])]
            query = select(table).where(*self._where(table, research))
            if after:
                query = query.where(tuple_(*ordering) > tuple_(*after[:len(ordering)]))
            rows = session.execute(query.order_by(*ordering).limit(limit + 1)).mappings().all()
            selected = [self._get(session, research, kind, row[identity], row[version] if version else None) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            import base64
            row = rows[limit - 1]
            values = [str(self.user_id), str(self.project_id), str(research), kind, row['created_at'].isoformat(), str(row[identity]), row[version] if version else 1]
            next_cursor = base64.urlsafe_b64encode(json.dumps(values, separators=(',', ':')).encode()).decode().rstrip('=')
        return selected, c.PageInfo(limit=limit, next_cursor=next_cursor)

    def latest_result(self, research, kind):
        run = self.get(research, 'run', research)
        pins = self.selections(research, 'run', research)['record']
        identity = getattr(run, kind + '_id')
        if identity is None:
            raise RecordNotFound('Research result has not been published')
        return self.get(research, kind, identity, pins[kind + '_version'])

    def approve_gap(self, research, gap_id, key, body):
        from app.db.workspace_models import actions
        fingerprint = hashlib.sha256(json.dumps([str(gap_id), body.model_dump(mode='json')], sort_keys=True).encode()).hexdigest()
        budget = ledger(self.database, self.user_id, self.project_id, research).snapshot()
        with self.database.transaction(self.user_id) as session:
            self._project(session, lock=True, write=True)
            self._research(session, research, lock=True)
            existing = session.execute(select(actions).where(*self._where(actions, research), actions.c.gap_id == gap_id)).mappings().one_or_none()
            if existing is not None:
                if existing['fingerprint'] != fingerprint:
                    raise JobConflict('Gap approval input differs')
                return c.GapApprovalReceipt(user_id=self.user_id, project_id=self.project_id, research_id=research,
                    gap=self._get(session, research, 'gap', gap_id, existing['gap_version']), run=self._get(session, research, 'run', research))
            gap = self._get(session, research, 'gap', gap_id, body.expected_gap_version)
            run = self._get(session, research, 'run', research)
            pins = self._row(session, research, 'run', research)
            if (gap.parent_report_id, gap.parent_report_version) != (body.expected_report_id, body.expected_report_version) or (run.report_id, pins['report_version']) != (gap.parent_report_id, gap.parent_report_version):
                raise JobConflict('Only a gap in the current report can continue research')
            if gap.kind != c.GapKind.INVESTIGATE_SECONDARY or gap.status != 'proposed' or gap.cycle >= gap.max_cycles:
                raise JobConflict('Only a finite proposed secondary gap can be dispatched')
            if run.status != 'completed' or run.cancel_requested or not gap.proposed_queries:
                raise JobConflict('Completed uncancelled research with proposed queries required')
            from app.budget_contract import ResourceAmount
            spent, held = ResourceAmount.from_json(budget['spent']), ResourceAmount.from_json(budget['held'])
            if budget['closed'] or budget['cancelled_at'] is not None or held.requests or spent.requests >= run.budget.max_requests or spent.tokens >= run.budget.max_tokens or __import__('decimal').Decimal(spent.cost_usd) >= __import__('decimal').Decimal(run.budget.max_cost_usd):
                raise JobConflict('Remaining shared budget is unavailable')
            if budget['started_at'] and (datetime.now(timezone.utc)-budget['started_at']).total_seconds() >= run.budget.max_duration_seconds:
                raise JobConflict('Shared research deadline expired')
            job = self._job_row(session, research, lock=True)
            approved = c.ResearchGapRequest.model_validate({**gap.model_dump(mode='json'), 'gap_version':gap.gap_version+1, 'status':'approved', 'created_at':datetime.now(timezone.utc)})
            writer = EvidenceWriter(self, session, research)
            writer.put_gap(approved)
            session.execute(actions.insert().values(user_id=self.user_id, project_id=self.project_id, research_id=research,
                gap_id=gap_id, gap_version=approved.gap_version, request_key=key, fingerprint=fingerprint, cycle=gap.cycle))
            session.execute(update(jobs.jobs).where(*self._where(jobs.jobs, research)).values(command={
                'op':'continue_gap','gap_id':str(gap_id),'gap_version':approved.gap_version,'request_key':str(key)}))
            executions = list(run.source_executions)
            for query in gap.proposed_queries:
                executions.append(c.QueryExecution(user_id=self.user_id, project_id=self.project_id, research_id=research,
                    created_at=approved.created_at, versions=run.versions, execution_id=uuid5(gap_id, str(query.query_id)),
                    query_id=query.query_id, source_id=query.source_id, attempt=gap.cycle+2, status='queued', counts=c.SourceCounts(),usage=c.Usage()))
            updated = c.ResearchRun.model_validate({**run.model_dump(mode='json'), 'status':'queued','phase':'planning','finished_at':None,
                'source_executions':[item.model_dump(mode='json') for item in executions]})
            writer.put_run(updated, bundle_version=pins['bundle_version'], report_version=pins['report_version'])
            writer.flush_associations()
            writer.seal()
            return c.GapApprovalReceipt(user_id=self.user_id, project_id=self.project_id, research_id=research, gap=approved, run=updated)
