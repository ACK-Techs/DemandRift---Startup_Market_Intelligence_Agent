"""Authenticated preparation HTTP against fresh PostgreSQL, without pipeline launch."""

import asyncio
from contextlib import contextmanager
import json
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.auth_body_guard import AuthBodyGuard
from app.auth_config import AuthPolicy
from app.auth_routes import router as auth_router
from app.auth_service import AuthService
from app.contracts import (
    BriefPage,
    IdeaBrief,
    PreparationMutationReceipt,
    ResearchPreparation,
    ResearchPreparationPage,
)
from app.http_errors import install_errors
from app.preparation_body_guard import PreparationBodyGuard
from app.preparation_routes import router

pytestmark = pytest.mark.postgres
ORIGIN = "http://127.0.0.1:3010"
IDEA = "  İstanbul araştırması\n🙂 e\u0301 \t "


@contextmanager
def client_for(db, root_path=""):
    # Root owns production registration/head checks; this harness exercises the
    # real existing session/auth handlers, native repository and both guards.
    app = FastAPI(root_path=root_path)
    app.state.auth_service = AuthService(db["app"], AuthPolicy(origins=(ORIGIN,)))
    install_errors(app)
    app.include_router(auth_router)
    app.include_router(router)
    app.add_middleware(AuthBodyGuard)
    app.add_middleware(PreparationBodyGuard)
    with TestClient(app, base_url="https://backend.example.invalid") as client:
        yield client


def account(client, email="preparation@example.invalid"):
    reply = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": "synthetic fixture password only"},
    )
    assert reply.status_code == 201
    session = reply.json()
    headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
    project = client.post(
        "/api/v1/projects", headers=headers, json={"name": "Preparation"}
    )
    assert project.status_code == 201
    return session, headers, "/api/v1/projects/" + project.json()["project_id"]


def create(client, base, headers, key=None, **body):
    return client.post(
        base + "/research",
        headers={**headers, "Idempotency-Key": str(key or uuid4())},
        json={"original_idea": IDEA, **body},
    )


def test_http_create_replay_recovery_human_edit_and_exact_history(postgres_database):
    with client_for(postgres_database) as client:
        session, headers, base = account(client)
        key = uuid4()
        response = create(client, base, headers, key)
        brief = IdeaBrief.model_validate(response.json())
        assert (
            response.status_code == 201
            and str(brief.user_id) == session["user"]["user_id"]
        )
        assert brief.content.original_idea == IDEA and brief.status == "awaiting_user"
        replay = create(client, base, headers, key)
        assert replay.status_code == 200 and replay.json() == response.json()
        receipt_reply = client.get(
            base + f"/preparation-mutations/create_research/{key}"
        )
        receipt = PreparationMutationReceipt.model_validate(receipt_reply.json())
        assert receipt.brief == brief
        rid = base + f"/research/{brief.research_id}"
        summary = ResearchPreparation.model_validate(client.get(rid).json())
        assert summary.latest_brief.brief_version == 1 and summary.original_idea == IDEA
        revision_key = uuid4()
        body = {
            "expected_brief_version": 1,
            "target_user": "  İnsan 🙂  ",
            "primary_category": "gelistirici-araci",
        }
        revised_reply = client.post(
            rid + "/briefs",
            headers={**headers, "Idempotency-Key": str(revision_key)},
            json=body,
        )
        changed = IdeaBrief.model_validate(revised_reply.json())
        assert revised_reply.status_code == 201 and changed.brief_version == 2
        assert changed.content.target_user.value == "  İnsan 🙂  "
        assert (
            changed.content.target_user.origin == "user_stated"
            and not changed.content.target_user.confirmed
        )
        assert (
            changed.content.category_origin == "user_stated"
            and not changed.content.category_confirmed
        )
        assert client.get(rid + "/briefs/latest").json() == revised_reply.json()
        assert (
            client.get(rid + f"/briefs/{brief.brief_id}/versions/1").json()
            == response.json()
        )
        assert BriefPage.model_validate(
            client.get(rid + "/briefs?limit=1").json()
        ).items == [changed]
        assert create(client, base, headers, key).json() == response.json()
        assert (
            PreparationMutationReceipt.model_validate(
                client.get(
                    base + f"/preparation-mutations/revise_brief/{revision_key}"
                ).json()
            ).brief
            == changed
        )
        for reply in (response, replay, receipt_reply, revised_reply, client.get(rid)):
            assert reply.headers["cache-control"] == "private, no-store"


def test_http_conflicts_single_key_and_no_identity_confirmation_input(
    postgres_database,
):
    with client_for(postgres_database) as client:
        _, headers, base = account(client)
        key = uuid4()
        brief = create(client, base, headers, key).json()
        assert (
            create(client, base, headers, key, original_idea=IDEA.strip()).status_code
            == 409
        )
        assert create(client, base, headers, user_id=str(uuid4())).status_code == 422
        for key_headers in (
            {},
            {"Idempotency-Key": "bad"},
            [("Idempotency-Key", str(uuid4())), ("Idempotency-Key", str(uuid4()))],
        ):
            combined = list(headers.items()) + (
                list(key_headers.items())
                if isinstance(key_headers, dict)
                else key_headers
            )
            reply = client.post(
                base + "/research", headers=combined, json={"original_idea": IDEA}
            )
            assert reply.status_code == 422
        rid = base + "/research/" + brief["research_id"]
        for forbidden in (
            {"original_idea": "new"},
            {"status": "confirmed"},
            {"target_user": {"value": "AI", "origin": "user_confirmed"}},
            {"ai_assumptions": []},
            {"user_id": str(uuid4())},
        ):
            reply = client.post(
                rid + "/briefs",
                headers={**headers, "Idempotency-Key": str(uuid4())},
                json={"expected_brief_version": 1, **forbidden},
            )
            assert reply.status_code == 422 and "AI" not in reply.text
        assert (
            client.post(
                rid + "/briefs",
                headers={**headers, "Idempotency-Key": str(uuid4())},
                json={"expected_brief_version": 2, "product_type": "tool"},
            ).status_code
            == 409
        )
        assert client.get(rid + "/briefs/latest").json() == brief


def test_http_session_origin_csrf_and_legacy_account_boundaries(postgres_database):
    with client_for(postgres_database) as client:
        session, headers, base = account(client)
        for supplied, expected in (
            ({}, 403),
            ({"Origin": ORIGIN}, 403),
            (
                {
                    "Origin": "https://evil.invalid",
                    "X-CSRF-Token": session["csrf_token"],
                },
                403,
            ),
        ):
            assert create(client, base, supplied).status_code == expected
        duplicate = list(headers.items()) + [("Origin", ORIGIN)]
        assert (
            client.post(
                base + "/research",
                headers=duplicate + [("Idempotency-Key", str(uuid4()))],
                json={"original_idea": IDEA},
            ).status_code
            == 403
        )
        assert client.get("/api/v1/auth/session").json() == session
        assert (
            client.get("/api/v1/projects").json()["items"][0]["project_id"]
            == base.rsplit("/", 1)[1]
        )
        assert create(client, base, headers).status_code == 201
        client.cookies.clear()
        reply = create(client, base, headers)
        assert (
            reply.status_code == 401
            and reply.headers["cache-control"] == "private, no-store"
        )
        assert client.get(base + "/research").status_code == 401


def test_http_foreign_unknown_archived_and_scoped_pages(postgres_database):
    db = postgres_database
    with client_for(db) as owner, client_for(db) as foreign:
        _, headers, base = account(owner)
        _, foreign_headers, foreign_base = account(foreign, "foreign@example.invalid")
        key = uuid4()
        brief = create(owner, base, headers, key).json()
        for path in (
            base + "/research/" + brief["research_id"],
            base + f"/preparation-mutations/create_research/{key}",
        ):
            assert foreign.get(path).status_code == 404
            assert owner.get(path.replace(base, foreign_base)).status_code == 404
        missing = owner.get(base + "/research/" + str(uuid4()))
        foreign_reply = foreign.get(base + "/research/" + brief["research_id"])
        assert (
            missing.status_code,
            missing.json()["code"],
            missing.json()["message"],
        ) == (
            foreign_reply.status_code,
            foreign_reply.json()["code"],
            foreign_reply.json()["message"],
        )
        assert create(foreign, base, foreign_headers).status_code == 404
        create(owner, base, headers)
        page = ResearchPreparationPage.model_validate(
            owner.get(base + "/research?limit=1").json()
        )
        assert page.page.next_cursor
        assert (
            foreign.get(
                foreign_base + "/research", params={"cursor": page.page.next_cursor}
            ).status_code
            == 422
        )
        next_page = ResearchPreparationPage.model_validate(
            owner.get(
                base + "/research", params={"cursor": page.page.next_cursor}
            ).json()
        )
        assert next_page.items[0].research_id != page.items[0].research_id
        with db["admin"].transaction() as sql:
            sql.execute(
                text(
                    "UPDATE public.projects SET archived_at=clock_timestamp() WHERE project_id=:p"
                ),
                {"p": UUID(base.rsplit("/", 1)[1])},
            )
        assert create(owner, base, headers, key).status_code == 404
        assert (
            owner.get(
                base + f"/preparation-mutations/create_research/{key}"
            ).status_code
            == 200
        )


def test_http_strict_body_boundaries_and_safe_errors(postgres_database):
    with client_for(postgres_database) as client:
        _, headers, base = account(client)
        headers = {
            **headers,
            "Idempotency-Key": str(uuid4()),
            "Content-Type": "application/json",
        }
        for body in (
            b'{"original_idea":"one","original_idea":"two"}',
            b'{"original_idea":"one","extra":NaN}',
            b'{"original_idea":"\\ud800"}',
            b'{"original_idea":"one","extra":1e999}',
            b"[]",
            b"{",
            b'{"original_idea":"\xff"}',
        ):
            reply = client.post(base + "/research", headers=headers, content=body)
            assert (
                reply.status_code == 422
                and reply.headers["cache-control"] == "private, no-store"
            )
            assert "one" not in reply.text and "two" not in reply.text
        assert (
            client.post(
                base + "/research",
                headers={**headers, "Content-Type": "text/plain"},
                content="idea",
            ).status_code
            == 415
        )
        assert (
            client.post(
                base + "/research",
                headers={**headers, "Content-Encoding": "gzip"},
                content=b"{}",
            ).status_code
            == 415
        )
        assert (
            client.post(
                base + "/research", headers=headers, content=b"x" * 65537
            ).status_code
            == 413
        )
        minimal = b'{"original_idea":"valid"}'
        assert (
            client.post(
                base + "/research",
                headers=headers,
                content=minimal + b" " * (65536 - len(minimal)),
            ).status_code
            == 201
        )
        assert (
            client.post(
                base + "/research",
                headers=list(headers.items())
                + [("Content-Length", "2"), ("Content-Length", "2")],
                content=b"{}",
            ).status_code
            == 413
        )
        assert client.get(base + "/research?limit=101").status_code == 422
        assert (
            client.put(base + "/research", headers=headers, content=b"{}").status_code
            == 405
        )


def test_http_corruption_is_safe_500_and_no_automatic_retry(postgres_database):
    db = postgres_database
    with client_for(db) as client:
        _, headers, base = account(client)
        key = uuid4()
        brief = create(client, base, headers, key).json()
        with db["admin"].transaction() as sql:
            sql.execute(
                text(
                    "ALTER TABLE public.idea_briefs DISABLE TRIGGER immutable_snapshot"
                )
            )
            sql.execute(
                text(
                    "UPDATE public.idea_briefs SET payload=jsonb_set(payload,'{content,product_type,value}',to_jsonb('private corrupt snapshot'::text)) WHERE brief_id=:b"
                ),
                {"b": UUID(brief["brief_id"])},
            )
            sql.execute(
                text("ALTER TABLE public.idea_briefs ENABLE TRIGGER immutable_snapshot")
            )
        for reply in (
            client.get(base + "/research/" + brief["research_id"] + "/briefs/latest"),
            create(client, base, headers, key),
            client.get(base + f"/preparation-mutations/create_research/{key}"),
        ):
            assert (
                reply.status_code == 500
                and "private corrupt snapshot" not in reply.text
            )
            assert (
                reply.json()["retryable"] is False
                and reply.headers["cache-control"] == "private, no-store"
            )
        with db["admin"].transaction() as sql:
            assert sql.scalar(text("SELECT count(*) FROM public.researches")) == 1


def test_asgi_chunked_limit_disconnect_and_root_path():
    # Raw ASGI chunks verify the limit before JSON parsing or downstream entry.
    async def exercise(
        chunks, path="/gateway/api/v1/projects/p/research", extra_headers=()
    ):
        sent, entered = [], []

        async def downstream(scope, receive, send):
            entered.append(True)
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return chunks.pop(0)

        async def send(message):
            sent.append(message)

        await PreparationBodyGuard(downstream)(
            {
                "type": "http",
                "path": path,
                "root_path": "/gateway",
                "method": "POST",
                "headers": [(b"content-type", b"application/json"), *extra_headers],
            },
            receive,
            send,
        )
        return sent, entered

    sent, entered = asyncio.run(
        exercise(
            [
                {"type": "http.request", "body": b"x" * 32768, "more_body": True},
                {"type": "http.request", "body": b"x" * 32769, "more_body": False},
            ]
        )
    )
    assert sent[0]["status"] == 413 and not entered
    assert json.loads(sent[1]["body"])["retryable"] is False
    assert (b"cache-control", b"private, no-store") in sent[0]["headers"]
    assert asyncio.run(exercise([{"type": "http.disconnect"}])) == ([], [])
    sent, entered = asyncio.run(
        exercise([{"type": "http.request", "body": b"{}", "more_body": False}])
    )
    assert sent[0]["status"] == 204 and entered
    sent, entered = asyncio.run(exercise([], path="/gateway/api/v1/auth/register"))
    assert sent[0]["status"] == 204 and entered
