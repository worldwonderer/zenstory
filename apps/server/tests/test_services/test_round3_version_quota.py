"""
Round3 G7（version-quota）服务层回归测试。

覆盖缺陷 #5：AI 写入的版本不计配额却占用户 per-file 版本额度，
免费用户十来次 AI 编辑之后，自己的建版本与回滚被永久锁死。
"""

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, select

from core.error_handler import APIException
from models import File, FileVersion, Project, User
from models.file_version import (
    CHANGE_SOURCE_AI,
    CHANGE_SOURCE_SYSTEM,
    CHANGE_SOURCE_USER,
    CHANGE_TYPE_AI_EDIT,
)
from models.subscription import SubscriptionPlan, UserSubscription
from services.core.auth_service import hash_password
from services.features.file_version_service import FileVersionService


def _make_user(db_session: Session, username: str) -> User:
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
    return user


def _bind_plan(db_session: Session, user: User, max_versions: int) -> SubscriptionPlan:
    """给用户绑定一个 per-file 版本上限为 max_versions 的订阅计划。"""
    plan = SubscriptionPlan(
        name=f"round3-version-quota-{user.id[:8]}",
        display_name="Round3 Version Quota",
        display_name_en="Round3 Version Quota",
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
    return plan


def _make_file(db_session: Session, user: User, content: str = "原始正文。") -> File:
    project = Project(name="Round3 Quota Project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    file = File(
        project_id=project.id,
        title="第一章",
        file_type="draft",
        content=content,
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.mark.integration
def test_get_version_count_filters_by_change_source(db_session: Session):
    """计数口径要能按来源过滤，否则配额判定必然把 AI 的行算进用户额度。"""
    user = _make_user(db_session, "r3q_count")
    file = _make_file(db_session, user)
    service = FileVersionService()

    for i in range(3):
        service.create_version(
            session=db_session,
            file_id=file.id,
            new_content=f"AI 第 {i} 版",
            change_type=CHANGE_TYPE_AI_EDIT,
            change_source=CHANGE_SOURCE_AI,
        )
    service.create_version(
        session=db_session,
        file_id=file.id,
        new_content="用户写的一版",
        change_source=CHANGE_SOURCE_USER,
    )
    service.create_version(
        session=db_session,
        file_id=file.id,
        new_content="系统写的一版",
        change_source=CHANGE_SOURCE_SYSTEM,
    )

    assert service.get_version_count(db_session, file.id) == 5
    assert (
        service.get_version_count(db_session, file.id, change_source=CHANGE_SOURCE_USER)
        == 1
    )
    assert (
        service.get_version_count(db_session, file.id, change_source=CHANGE_SOURCE_AI)
        == 3
    )
    assert (
        service.get_version_count(
            db_session, file.id, change_source=CHANGE_SOURCE_SYSTEM
        )
        == 1
    )


@pytest.mark.integration
def test_ai_versions_do_not_consume_user_version_quota(db_session: Session):
    """AI/系统写入的版本不占用户额度：用户的额度只被自己的版本消耗。"""
    user = _make_user(db_session, "r3q_aiquota")
    _bind_plan(db_session, user, max_versions=2)
    file = _make_file(db_session, user)
    service = FileVersionService()

    # AI 连写 5 版（agent 侧就是这样调用的：不传 user_id，change_source=ai）
    for i in range(5):
        service.create_version(
            session=db_session,
            file_id=file.id,
            new_content=f"AI 续写 {i}",
            change_type=CHANGE_TYPE_AI_EDIT,
            change_source=CHANGE_SOURCE_AI,
        )

    # 用户仍然拿得到自己的 2 个额度
    for i in range(2):
        service.create_version(
            session=db_session,
            file_id=file.id,
            new_content=f"用户手写 {i}",
            change_source=CHANGE_SOURCE_USER,
            user_id=user.id,
        )

    has_quota, used, limit = service.check_user_version_quota(
        db_session, file.id, user.id
    )
    assert (has_quota, used, limit) == (False, 2, 2)

    # 第 3 个用户版本才应该被拒绝，且理由是用户自己写满了，与 AI 无关
    with pytest.raises(APIException) as exc_info:
        service.create_version(
            session=db_session,
            file_id=file.id,
            new_content="用户手写 2",
            change_source=CHANGE_SOURCE_USER,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 402


@pytest.mark.integration
def test_rollback_restores_content_without_bypassing_version_quota(
    db_session: Session,
):
    """At full quota rollback succeeds but cannot create unlimited base rows."""
    user = _make_user(db_session, "r3q_rollback")
    _bind_plan(db_session, user, max_versions=1)
    file = _make_file(db_session, user, content="原始正文：好好的一章。")
    service = FileVersionService()

    service.create_version(
        session=db_session,
        file_id=file.id,
        new_content="原始正文：好好的一章。",
        change_source=CHANGE_SOURCE_USER,
        user_id=user.id,
    )
    for i in range(3):
        service.create_version(
            session=db_session,
            file_id=file.id,
            new_content=f"AI 把正文改坏了 {i}。",
            change_type=CHANGE_TYPE_AI_EDIT,
            change_source=CHANGE_SOURCE_AI,
        )
    file.content = "AI 把正文改坏了 2。"
    db_session.add(file)
    db_session.commit()

    # 额度此刻已满（用户版本 1/1），回滚仍然必须成功
    assert service.check_user_version_quota(db_session, file.id, user.id)[0] is False

    restored_file, new_version, version_quota_exceeded = service.rollback_to_version(
        db_session, file.id, 1, user_id=user.id
    )
    assert restored_file.content == "原始正文：好好的一章。"
    assert new_version is None
    assert version_quota_exceeded is True

    db_session.expire_all()
    assert db_session.get(File, file.id).content == "原始正文：好好的一章。"
    versions = db_session.exec(
        select(FileVersion).where(FileVersion.file_id == file.id)
    ).all()
    assert len(versions) == 4
