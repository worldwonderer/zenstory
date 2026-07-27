"""第三轮 deep review 的**补丁组** API 回归测试。

覆盖：POST /api/v1/files/{id}/versions 的配额绕过口子。

bug-05 的修复把配额闸门收窄成 `change_source == user`，而该端点的
`CreateVersionRequest.change_source` 是**纯客户端可控**的字段并被原样透传，
于是任何登录用户只要发 {"change_source": "ai"} 就能同时绕过：
  1) 闸门（只拦 user 来源）
  2) 计数（check_user_version_quota 只数 user 来源的行）
file_versions_per_file 因此形同虚设。修复前该端点无论 change_source 取何值
都会被配额拦住，属于本次修复引入的回退。
"""

import asyncio
import contextlib
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from database import get_session
from main import app
from models import File, FileVersion, Project, User
from models.file_version import CHANGE_SOURCE_USER
from models.subscription import SubscriptionPlan, UserSubscription
from services.core.auth_service import hash_password


@contextlib.contextmanager
def _independent_request_sessions(db_session: Session):
    """Make concurrent ASGI requests use production-like, distinct DB sessions.

    The shared ``client`` fixture intentionally reuses ``db_session`` for ordinary
    request/assertion convenience. Sharing one SQLAlchemy Session across worker
    threads is invalid, though, and can turn a real concurrency assertion into a
    Session state-machine failure before the per-file lock is exercised.
    """
    previous_override = app.dependency_overrides.get(get_session)
    engine = db_session.get_bind()

    def override_get_session():
        with Session(engine, expire_on_commit=False) as request_session:
            yield request_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_override


async def _setup_user(client: AsyncClient, db_session: Session, username: str):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await client.post(
        "/api/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    project = Project(name="Round3 patch project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    file = File(
        project_id=project.id,
        title="第一章",
        file_type="draft",
        content="原始正文。",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)

    return user, file, headers


def _bind_plan(db_session: Session, user: User, max_versions: int) -> None:
    plan = SubscriptionPlan(
        name=f"round3-patch-{user.id[:8]}",
        display_name="Round3 patch",
        display_name_en="Round3 patch",
        price_monthly_cents=999,
        price_yearly_cents=9999,
        features={"file_versions_per_file": max_versions},
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    now = datetime.utcnow()
    db_session.add(
        UserSubscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
        )
    )
    db_session.commit()


@pytest.mark.integration
@pytest.mark.parametrize("spoofed_source", ["ai", "system"])
async def test_post_version_cannot_bypass_quota_via_change_source(
    client: AsyncClient, db_session: Session, spoofed_source: str
):
    """伪造 change_source 不得绕过 per-file 版本额度：超额仍应 402。"""
    user, file, headers = await _setup_user(
        client, db_session, f"r3p_quota_{spoofed_source}"
    )
    _bind_plan(db_session, user, max_versions=2)

    for i in range(2):
        resp = await client.post(
            f"/api/v1/files/{file.id}/versions",
            json={"content": f"第 {i} 版", "change_source": spoofed_source},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        # 来源由服务端钉死成 user：否则闸门与计数会落在不同集合上
        assert resp.json()["change_source"] == CHANGE_SOURCE_USER

    blocked = await client.post(
        f"/api/v1/files/{file.id}/versions",
        json={"content": "第 3 版", "change_source": spoofed_source},
        headers=headers,
    )
    assert blocked.status_code == 402, blocked.text

    db_session.expire_all()
    rows = db_session.exec(
        select(FileVersion).where(FileVersion.file_id == file.id)
    ).all()
    assert len(rows) == 2
    assert all(row.change_source == CHANGE_SOURCE_USER for row in rows)


@pytest.mark.integration
async def test_post_version_still_enforces_quota_for_plain_user_source(
    client: AsyncClient, db_session: Session
):
    """不传 change_source（默认 user）的既有行为不受影响。"""
    user, file, headers = await _setup_user(client, db_session, "r3p_quota_plain")
    _bind_plan(db_session, user, max_versions=1)

    ok = await client.post(
        f"/api/v1/files/{file.id}/versions",
        json={"content": "第 0 版"},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text

    blocked = await client.post(
        f"/api/v1/files/{file.id}/versions",
        json={"content": "第 1 版"},
        headers=headers,
    )
    assert blocked.status_code == 402, blocked.text


@pytest.mark.integration
async def test_post_version_rejects_unknown_change_source(
    client: AsyncClient, db_session: Session
):
    """change_source 收窄成枚举后，任意字符串必须被 422 拒绝，
    不能再原样落库成脏数据。"""
    _, file, headers = await _setup_user(client, db_session, "r3p_quota_enum")

    resp = await client.post(
        f"/api/v1/files/{file.id}/versions",
        json={"content": "正文", "change_source": "definitely-not-a-source"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
@pytest.mark.parametrize("spoofed_source", ["ai", "system"])
async def test_put_file_cannot_bypass_quota_via_change_source(
    client: AsyncClient, db_session: Session, spoofed_source: str
):
    """PUT 与 POST 一样不得让客户端来源逃离受限版本计数集合。"""
    user, file, headers = await _setup_user(
        client,
        db_session,
        f"r3p_put_quota_{spoofed_source}",
    )
    _bind_plan(db_session, user, max_versions=1)

    first = await client.put(
        f"/api/v1/files/{file.id}",
        json={"content": "第一版", "change_source": spoofed_source},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["version_quota_exceeded"] is False

    second = await client.put(
        f"/api/v1/files/{file.id}",
        json={"content": "第二版", "change_source": spoofed_source},
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["version_quota_exceeded"] is True

    db_session.expire_all()
    rows = db_session.exec(
        select(FileVersion).where(FileVersion.file_id == file.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].change_source == CHANGE_SOURCE_USER


@pytest.mark.integration
async def test_concurrent_authenticated_writes_cannot_overrun_single_version_slot(
    client: AsyncClient,
    db_session: Session,
):
    """两个并发 PUT 的预检都看到余额时，最终也只能有一个用户快照。"""
    user, file, headers = await _setup_user(
        client,
        db_session,
        "r3p_put_quota_race",
    )
    _bind_plan(db_session, user, max_versions=1)

    with _independent_request_sessions(db_session):
        responses = await asyncio.gather(
            client.put(
                f"/api/v1/files/{file.id}",
                json={"content": "并发第一版", "change_source": "ai"},
                headers=headers,
            ),
            client.put(
                f"/api/v1/files/{file.id}",
                json={"content": "并发第二版", "change_source": "system"},
                headers=headers,
            ),
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(
        response.json()["version_quota_exceeded"] for response in responses
    ) == [False, True]

    db_session.expire_all()
    rows = db_session.exec(
        select(FileVersion).where(FileVersion.file_id == file.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].change_source == CHANGE_SOURCE_USER


@pytest.mark.integration
async def test_put_reports_quota_race_as_saved_content_without_snapshot(
    client: AsyncClient,
    db_session: Session,
    monkeypatch,
):
    """首轮预检后余额被并发请求占用时，正文成功、快照跳过且响应不谎报失败。"""
    user, file, headers = await _setup_user(
        client,
        db_session,
        "r3p_put_quota_race_contract",
    )
    _bind_plan(db_session, user, max_versions=1)

    checks = 0

    def staged_quota_check(_service, _session, _file_id, _user_id):
        nonlocal checks
        checks += 1
        return (True, 0, 1) if checks == 1 else (False, 1, 1)

    monkeypatch.setattr(
        "services.features.file_version_service.FileVersionService.check_user_version_quota",
        staged_quota_check,
    )

    response = await client.put(
        f"/api/v1/files/{file.id}",
        json={"content": "正文已经保存，但最后一个版本位被并发请求占用。"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["version_quota_exceeded"] is True
    assert checks == 2
    db_session.expire_all()
    assert db_session.get(File, file.id).content.startswith("正文已经保存")
    assert (
        db_session.exec(
            select(FileVersion).where(FileVersion.file_id == file.id)
        ).all()
        == []
    )


@pytest.mark.integration
async def test_concurrent_post_versions_cannot_overrun_single_version_slot(
    client: AsyncClient,
    db_session: Session,
):
    """显式建版本入口的配额检查与插入也必须按文件串行化。"""
    user, file, headers = await _setup_user(
        client,
        db_session,
        "r3p_post_quota_race",
    )
    _bind_plan(db_session, user, max_versions=1)

    with _independent_request_sessions(db_session):
        responses = await asyncio.gather(
            client.post(
                f"/api/v1/files/{file.id}/versions",
                json={"content": "并发第一版", "change_source": "ai"},
                headers=headers,
            ),
            client.post(
                f"/api/v1/files/{file.id}/versions",
                json={"content": "并发第二版", "change_source": "system"},
                headers=headers,
            ),
        )

    assert sorted(response.status_code for response in responses) == [200, 402]
    db_session.expire_all()
    rows = db_session.exec(
        select(FileVersion).where(FileVersion.file_id == file.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].change_source == CHANGE_SOURCE_USER
