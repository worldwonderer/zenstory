from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from models import (
    UPGRADE_FUNNEL_ACTION_CLICK,
    UPGRADE_FUNNEL_ACTION_CONVERSION,
    UPGRADE_FUNNEL_ACTION_EXPOSE,
    UpgradeFunnelEvent,
    User,
)
from services.core.auth_service import hash_password
from services.features.upgrade_funnel_event_service import upgrade_funnel_event_service


def _create_user(db_session: Session) -> User:
    user = User(
        email="funnel@example.com",
        username="funnel-user",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_record_event_normalizes_destination_and_occurred_at(db_session: Session):
    user = _create_user(db_session)
    naive_dt = datetime.utcnow()

    event = upgrade_funnel_event_service.record_event(
        db_session,
        user_id=user.id,
        action=UPGRADE_FUNNEL_ACTION_CLICK,
        source=" pricing_banner ",
        surface="page",
        cta="primary",
        destination="   ",
        occurred_at=naive_dt,
    )

    assert event.source == "pricing_banner"
    assert event.destination is None
    assert event.occurred_at.replace(tzinfo=UTC) == naive_dt.replace(tzinfo=UTC)


def test_get_funnel_stats_clamps_days_and_calculates_rates(db_session: Session):
    user = _create_user(db_session)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            UpgradeFunnelEvent(
                user_id=user.id,
                event_name="upgrade_funnel_expose",
                action=UPGRADE_FUNNEL_ACTION_EXPOSE,
                source="pricing",
                surface="page",
                occurred_at=now - timedelta(days=1),
            ),
            UpgradeFunnelEvent(
                user_id=user.id,
                event_name="upgrade_funnel_click",
                action=UPGRADE_FUNNEL_ACTION_CLICK,
                source="pricing",
                surface="page",
                occurred_at=now - timedelta(days=1),
            ),
            UpgradeFunnelEvent(
                user_id=user.id,
                event_name="upgrade_funnel_conversion",
                action=UPGRADE_FUNNEL_ACTION_CONVERSION,
                source="pricing",
                surface="page",
                occurred_at=now - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    stats = upgrade_funnel_event_service.get_funnel_stats(db_session, days=365)

    assert stats["window_days"] == 90
    assert stats["totals"] == {"expose": 1, "click": 1, "conversion": 1}
    assert stats["sources"][0]["source"] == "pricing"
    assert stats["sources"][0]["click_through_rate"] == 1.0
    assert stats["sources"][0]["conversion_rate_from_click"] == 1.0
    assert stats["sources"][0]["conversion_rate_from_expose"] == 1.0
