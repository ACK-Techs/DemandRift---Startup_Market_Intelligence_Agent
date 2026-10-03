"""Real owner-scoped dashboard and supported persistent research preferences."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from app import contracts as c
from app.auth_routes import authenticated, verified_mutation, service
from app.preparation_routes import execute
from app.db.workspace_models import settings
from app.research_runtime import AUTHORIZED_LIMITS, validate_budget

router = APIRouter(prefix='/api/v1', tags=['workspace'])


@router.get('/settings', response_model=c.UserSettings)
def read_settings(request: Request, response: Response, auth=Depends(authenticated)):
    response.headers['Cache-Control'] = 'private, no-store'
    with service(request).database.transaction(auth.user.user_id) as session:
        row = session.execute(select(settings).where(settings.c.user_id == auth.user.user_id)).mappings().one_or_none()
    return c.UserSettings(user_id=auth.user.user_id, updated_at=row['updated_at'] if row else None,
        **(row['payload'] if row else dict(default_research_mode='standard', language_scope=['tr','en'], default_budget=AUTHORIZED_LIMITS)))


@router.patch('/settings', response_model=c.UserSettings)
def save_settings(body: c.UserSettingsUpdate, request: Request, response: Response, auth=Depends(verified_mutation)):
    def save():
        validate_budget(body.default_budget)
        if set(body.language_scope)-{'tr','en'} or len(set(body.language_scope)) != len(body.language_scope):
            raise ValueError('Supported unique languages required')
        stamp = datetime.now(timezone.utc)
        with service(request).database.transaction(auth.user.user_id) as session:
            command = insert(settings).values(user_id=auth.user.user_id, payload=body.model_dump(mode='json'), updated_at=stamp)
            session.execute(command.on_conflict_do_update(index_elements=[settings.c.user_id],set_={'payload':command.excluded.payload,'updated_at':stamp}))
        return c.UserSettings(user_id=auth.user.user_id, updated_at=stamp, **body.model_dump(mode='json'))
    response.headers['Cache-Control']='private, no-store'
    return execute(save)


@router.get('/dashboard', response_model=c.DashboardSummary)
def dashboard(request: Request, response: Response, auth=Depends(authenticated)):
    owner = auth.user.user_id
    with service(request).database.transaction(owner) as session:
        counts = session.execute(text('''SELECT (SELECT count(*) FROM projects WHERE user_id=:owner AND archived_at IS NULL) AS projects,
            (SELECT count(*) FROM researches WHERE user_id=:owner) AS researches'''), {'owner':owner}).mappings().one()
        statuses = session.execute(text("SELECT payload->>'status' AS name,count(*) AS amount FROM research_runs WHERE user_id=:owner GROUP BY 1"), {'owner':owner}).mappings().all()
        outcomes = session.execute(text("SELECT d.payload->>'outcome' AS name,count(*) AS amount FROM research_runs r JOIN decision_reports d ON (d.user_id,d.project_id,d.research_id,d.report_id,d.report_version)=(r.user_id,r.project_id,r.research_id,r.report_id,r.report_version) WHERE r.user_id=:owner GROUP BY 1"), {'owner':owner}).mappings().all()
        recent = session.execute(text('''SELECT p.project_id,p.name AS project_name,r.research_id,r.original_idea,
            COALESCE(run.payload->>'status','preparation') AS status,d.payload->>'outcome' AS outcome,r.created_at AS updated_at
            FROM researches r JOIN projects p USING(user_id,project_id)
            LEFT JOIN research_runs run USING(user_id,project_id,research_id)
            LEFT JOIN decision_reports d ON (d.user_id,d.project_id,d.research_id,d.report_id,d.report_version)=(run.user_id,run.project_id,run.research_id,run.report_id,run.report_version)
            WHERE r.user_id=:owner ORDER BY r.created_at DESC,r.research_id DESC LIMIT 20'''), {'owner':owner}).mappings().all()
    response.headers['Cache-Control']='private, no-store'
    return c.DashboardSummary(user_id=owner, active_projects=counts['projects'],research_count=counts['researches'],
        run_status_counts={row['name']:row['amount'] for row in statuses},outcome_counts={row['name']:row['amount'] for row in outcomes},
        recent=[c.DashboardResearch.model_validate(dict(row)) for row in recent],checked_at=datetime.now(timezone.utc))
