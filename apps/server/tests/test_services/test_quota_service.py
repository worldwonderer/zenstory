"""
Tests for QuotaService.

Unit tests for the quota management service, covering:
- User quota retrieval
- Plan-based limit checking
- AI conversation quota management
- Feature quota management
- Quota reset logic
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session

from models import User
from models.subscription import SubscriptionPlan, UsageQuota, UserSubscription
from services.quota_service import FEATURE_QUOTA_MAP, quota_service


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user for quota testing."""
    user = User(
        email="quota@example.com",
        username="quotauser",
        hashed_password="hashed_password",
        name="Quota Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def free_plan(db_session: Session):
    """Create a free subscription plan."""
    plan = SubscriptionPlan(
        name="free",
        display_name="Free",
        display_name_en="Free",
        price_monthly_cents=0,
        price_yearly_cents=0,
        features={
            "ai_conversations_per_day": 20,
            "max_projects": 3,
            "materials_library_access": False,
            "material_uploads": 0,
            "material_decompositions": 0,
            "custom_skills": 3,
            "inspiration_copies_monthly": 10,
        },
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def pro_plan(db_session: Session):
    """Create a pro subscription plan."""
    plan = SubscriptionPlan(
        name="pro",
        display_name="Pro",
        display_name_en="Pro",
        price_monthly_cents=2900,
        price_yearly_cents=29000,
        features={
            "ai_conversations_per_day": -1,  # unlimited
            "max_projects": -1,
            "materials_library_access": True,
            "material_uploads": 5,
            "material_decompositions": 5,
            "custom_skills": -1,
            "inspiration_copies_monthly": -1,
        },
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.mark.unit
class TestGetUserQuota:
    """Tests for get_user_quota method."""

    def test_get_user_quota_no_quota(self, db_session: Session, test_user):
        """Test getting quota for user without quota record."""
        result = quota_service.get_user_quota(db_session, test_user.id)

        assert result is None

    def test_get_user_quota_with_quota(self, db_session: Session, test_user):
        """Test getting quota for user with quota record."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=5,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        result = quota_service.get_user_quota(db_session, test_user.id)

        assert result is not None
        assert result.user_id == test_user.id
        assert result.ai_conversations_used == 5


@pytest.mark.unit
class TestGetUserPlan:
    """Tests for get_user_plan method."""

    def test_get_user_plan_free_default(self, db_session: Session, test_user, free_plan):
        """Test that users without subscription get free plan."""
        result = quota_service.get_user_plan(db_session, test_user.id)

        assert result is not None
        assert result.name == "free"

    def test_get_user_plan_with_subscription(
        self, db_session: Session, test_user, free_plan, pro_plan
    ):
        """Test getting plan for user with active subscription."""
        now = datetime.utcnow()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db_session.add(subscription)
        db_session.commit()

        result = quota_service.get_user_plan(db_session, test_user.id)

        assert result is not None
        assert result.name == "pro"

    def test_get_user_plan_expired_subscription(
        self, db_session: Session, test_user, free_plan, pro_plan
    ):
        """Test that expired subscription returns free plan."""
        now = datetime.utcnow()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status="active",
            current_period_start=now - timedelta(days=60),
            current_period_end=now - timedelta(days=30),  # Expired
        )
        db_session.add(subscription)
        db_session.commit()

        result = quota_service.get_user_plan(db_session, test_user.id)

        assert result is not None
        assert result.name == "free"

    def test_get_user_plan_cancelled_subscription(
        self, db_session: Session, test_user, free_plan, pro_plan
    ):
        """Test that cancelled subscription returns free plan."""
        now = datetime.utcnow()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status="cancelled",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db_session.add(subscription)
        db_session.commit()

        result = quota_service.get_user_plan(db_session, test_user.id)

        assert result is not None
        assert result.name == "free"


@pytest.mark.unit
class TestGetPlanLimits:
    """Tests for get_plan_limits method."""

    def test_get_plan_limits_free(self, db_session: Session, free_plan):
        """Test getting limits for free plan."""
        result = quota_service.get_plan_limits(free_plan)

        assert result is not None
        assert result["ai_conversations_per_day"] == 20
        assert result["max_projects"] == 3

    def test_get_plan_limits_pro(self, db_session: Session, pro_plan):
        """Test getting limits for pro plan."""
        result = quota_service.get_plan_limits(pro_plan)

        assert result is not None
        assert result["ai_conversations_per_day"] == -1  # Unlimited
        assert result["max_projects"] == -1  # Unlimited


@pytest.mark.unit
class TestFeatureAccess:
    def test_has_feature_access_defaults_to_false_for_free(self, db_session: Session, test_user, free_plan):
        assert quota_service.has_feature_access(
            db_session,
            test_user.id,
            "materials_library_access",
        ) is False

    def test_has_feature_access_true_for_paid(self, db_session: Session, test_user, pro_plan):
        now = datetime.utcnow()
        db_session.add(
            UserSubscription(
                user_id=test_user.id,
                plan_id=pro_plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        db_session.commit()

        assert quota_service.has_feature_access(
            db_session,
            test_user.id,
            "materials_library_access",
        ) is True

    def test_has_feature_access_falls_back_to_default_when_flag_missing(self, db_session: Session, test_user):
        plan = SubscriptionPlan(
            name="custom-default",
            display_name="Custom Default",
            display_name_en="Custom Default",
            price_monthly_cents=0,
            price_yearly_cents=0,
            features={"other_feature": True},
            is_active=True,
        )
        now = datetime.utcnow()
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)
        db_session.add(
            UserSubscription(
                user_id=test_user.id,
                plan_id=plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        db_session.commit()

        assert quota_service.has_feature_access(db_session, test_user.id, "materials_library_access") is False
        assert quota_service.has_feature_access(
            db_session,
            test_user.id,
            "materials_library_access",
            default=True,
        ) is True

    def test_has_feature_access_infers_materials_access_from_legacy_limits(self, db_session: Session, test_user):
        plan = SubscriptionPlan(
            name="legacy-materials",
            display_name="Legacy Materials",
            display_name_en="Legacy Materials",
            price_monthly_cents=0,
            price_yearly_cents=0,
            features={"material_decompositions": 2},
            is_active=True,
        )
        now = datetime.utcnow()
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)
        db_session.add(
            UserSubscription(
                user_id=test_user.id,
                plan_id=plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        db_session.commit()

        assert quota_service.has_feature_access(
            db_session,
            test_user.id,
            "materials_library_access",
        ) is True


@pytest.mark.unit
class TestCheckAIConversationQuota:
    """Tests for check_ai_conversation_quota method."""

    def test_check_quota_no_quota_record(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota when user has no quota record."""
        allowed, used, limit = quota_service.check_ai_conversation_quota(
            db_session, test_user.id
        )

        # Should create quota and return defaults
        assert allowed is True
        assert used == 0
        assert limit == 20  # Free plan limit

    def test_check_quota_within_limit(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota when within limit."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=10,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_ai_conversation_quota(
            db_session, test_user.id
        )

        assert allowed is True
        assert used == 10
        assert limit == 20

    def test_check_quota_at_limit(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota when at limit."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=20,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_ai_conversation_quota(
            db_session, test_user.id
        )

        assert allowed is False
        assert used == 20
        assert limit == 20

    def test_check_quota_unlimited(
        self, db_session: Session, test_user, pro_plan
    ):
        """Test checking quota for unlimited plan."""
        now = datetime.utcnow()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db_session.add(subscription)

        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=1000,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_ai_conversation_quota(
            db_session, test_user.id
        )

        assert allowed is True
        assert limit == -1  # Unlimited


@pytest.mark.unit
class TestConsumeAIConversation:
    """Tests for consume_ai_conversation method."""

    def test_consume_within_limit(
        self, db_session: Session, test_user, free_plan
    ):
        """Test consuming quota when within limit."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=5,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        result = quota_service.consume_ai_conversation(db_session, test_user.id)

        assert result is True

        # Verify increment
        db_session.refresh(quota)
        assert quota.ai_conversations_used == 6

    def test_consume_at_limit(
        self, db_session: Session, test_user, free_plan
    ):
        """Test consuming quota when at limit."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=20,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        result = quota_service.consume_ai_conversation(db_session, test_user.id)

        assert result is False

        # Verify no increment
        db_session.refresh(quota)
        assert quota.ai_conversations_used == 20

    def test_consume_creates_quota(
        self, db_session: Session, test_user, free_plan
    ):
        """Test that consuming creates quota if not exists."""
        # This should work because check_quota creates the record
        result = quota_service.consume_ai_conversation(db_session, test_user.id)

        assert result is True

        # Verify quota was created
        quota = quota_service.get_user_quota(db_session, test_user.id)
        assert quota is not None
        assert quota.ai_conversations_used == 1


@pytest.mark.unit
class TestReleaseAIConversation:
    """Tests for release_ai_conversation compensation method."""

    def test_release_decrements_usage(
        self, db_session: Session, test_user
    ):
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=3,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        released = quota_service.release_ai_conversation(db_session, test_user.id)
        assert released is True
        db_session.refresh(quota)
        assert quota.ai_conversations_used == 2

    def test_release_noop_when_usage_zero(
        self, db_session: Session, test_user
    ):
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=0,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        released = quota_service.release_ai_conversation(db_session, test_user.id)
        assert released is False
        db_session.refresh(quota)
        assert quota.ai_conversations_used == 0

    def test_release_checks_period_reset_before_decrement(
        self,
        db_session: Session,
        test_user,
    ):
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now - timedelta(days=1),
            period_end=now - timedelta(seconds=1),
            ai_conversations_used=2,
            last_reset_at=now - timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        with patch.object(
            quota_service,
            "_reset_quota_if_needed",
            wraps=quota_service._reset_quota_if_needed,
        ) as mock_reset:
            released = quota_service.release_ai_conversation(db_session, test_user.id)

        assert released is False
        assert mock_reset.call_count == 1


@pytest.mark.unit
class TestCreateDefaultQuota:
    """Tests for create_default_quota method."""

    def test_create_default_quota(self, db_session: Session, test_user):
        """Test creating default quota for user."""
        result = quota_service.create_default_quota(db_session, test_user.id)

        assert result is not None
        assert result.user_id == test_user.id
        assert result.ai_conversations_used == 0
        assert result.period_start is not None
        assert result.period_end is not None
        assert result.last_reset_at is not None

    def test_create_default_quota_period(self, db_session: Session, test_user):
        """Test that default quota has correct period."""
        result = quota_service.create_default_quota(db_session, test_user.id)

        # Daily window should be 24 hours
        delta = result.period_end - result.period_start
        assert delta == timedelta(hours=24)


@pytest.mark.unit
class TestCheckFeatureQuota:
    """Tests for check_feature_quota method."""

    def test_check_feature_quota_valid_type(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota for valid feature type with zero-limit free access."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_uploads_used=0,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=1),
            monthly_period_end=now + timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_feature_quota(
            db_session, test_user.id, "material_upload"
        )

        assert allowed is False
        assert used == 0
        assert limit == 0

    def test_check_feature_quota_invalid_type(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota for invalid feature type."""
        with pytest.raises(ValueError) as exc_info:
            quota_service.check_feature_quota(
                db_session, test_user.id, "invalid_feature"
            )

        assert "Unknown feature type" in str(exc_info.value)

    def test_check_feature_quota_at_limit(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking feature quota at zero limit."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_uploads_used=0,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=1),
            monthly_period_end=now + timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_feature_quota(
            db_session, test_user.id, "material_upload"
        )

        assert allowed is False
        assert used == 0
        assert limit == 0

    def test_check_feature_quota_paid_limit(
        self, db_session: Session, test_user, pro_plan
    ):
        """Test checking feature quota for a paid plan with a finite configured limit."""
        now = datetime.utcnow()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db_session.add(subscription)

        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_decompositions_used=4,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=1),
            monthly_period_end=now + timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        allowed, used, limit = quota_service.check_feature_quota(
            db_session, test_user.id, "material_decompose"
        )

        assert allowed is True
        assert used == 4
        assert limit == 5

    def test_check_all_feature_types(
        self, db_session: Session, test_user, free_plan
    ):
        """Test checking quota for all valid feature types."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_uploads_used=0,
            material_decompositions_used=0,
            skill_creates_used=0,
            inspiration_copies_used=0,
            last_reset_at=now,
        )
        db_session.add(quota)
        db_session.commit()

        for feature_type in FEATURE_QUOTA_MAP.keys():
            allowed, used, limit = quota_service.check_feature_quota(
                db_session, test_user.id, feature_type
            )

            expected_allowed = limit == -1 or limit > used
            assert allowed is expected_allowed
            assert used == 0
            assert limit >= 0 or limit == -1


@pytest.mark.unit
class TestConsumeFeatureQuota:
    """Tests for consume_feature_quota method."""

    def test_consume_feature_within_limit(
        self, db_session: Session, test_user, pro_plan
    ):
        """Test consuming feature quota when within limit."""
        now = datetime.utcnow()
        db_session.add(
            UserSubscription(
                user_id=test_user.id,
                plan_id=pro_plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_decompositions_used=2,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=1),
            monthly_period_end=now + timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        result = quota_service.consume_feature_quota(
            db_session, test_user.id, "material_decompose"
        )

        assert result is True

        # Verify increment
        db_session.refresh(quota)
        assert quota.material_decompositions_used == 3

    def test_consume_feature_at_limit(
        self, db_session: Session, test_user, pro_plan
    ):
        """Test consuming feature quota when at limit."""
        now = datetime.utcnow()
        db_session.add(
            UserSubscription(
                user_id=test_user.id,
                plan_id=pro_plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_decompositions_used=5,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=1),
            monthly_period_end=now + timedelta(days=1),
        )
        db_session.add(quota)
        db_session.commit()

        result = quota_service.consume_feature_quota(
            db_session, test_user.id, "material_decompose"
        )

        assert result is False

        # Verify no increment
        db_session.refresh(quota)
        assert quota.material_decompositions_used == 5

    def test_consume_feature_invalid_type(
        self, db_session: Session, test_user, free_plan
    ):
        """Test consuming feature quota with invalid type."""
        with pytest.raises(ValueError):
            quota_service.consume_feature_quota(
                db_session, test_user.id, "invalid_feature"
            )


@pytest.mark.unit
class TestQuotaReset:
    """Tests for quota reset logic."""

    def test_reset_quota_if_needed_same_day(
        self, db_session: Session, test_user, free_plan
    ):
        """Test that quota is not reset within same day."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            ai_conversations_used=15,
            last_reset_at=now,  # Just reset
        )
        db_session.add(quota)
        db_session.commit()

        # Check quota (which triggers reset check)
        quota_service.check_ai_conversation_quota(db_session, test_user.id)

        db_session.refresh(quota)
        # Should not reset
        assert quota.ai_conversations_used == 15

    def test_reset_quota_if_needed_after_24h(
        self, db_session: Session, test_user, free_plan
    ):
        """Test that quota resets after 24 hours."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now - timedelta(days=2),
            period_end=now + timedelta(days=28),
            ai_conversations_used=20,
            last_reset_at=now - timedelta(hours=25),  # 25 hours ago
        )
        db_session.add(quota)
        db_session.commit()

        # Check quota (which triggers reset check)
        allowed, used, _ = quota_service.check_ai_conversation_quota(
            db_session, test_user.id
        )

        db_session.refresh(quota)
        # Should have reset
        assert quota.ai_conversations_used == 0
        assert allowed is True
        assert used == 0

    def test_reset_monthly_quota(self, db_session: Session, test_user, free_plan):
        """Test monthly quota reset."""
        now = datetime.utcnow()
        quota = UsageQuota(
            user_id=test_user.id,
            period_start=now,
            period_end=now + timedelta(days=30),
            material_uploads_used=10,
            material_decompositions_used=5,
            skill_creates_used=3,
            inspiration_copies_used=10,
            last_reset_at=now,
            monthly_period_start=now - timedelta(days=31),
            monthly_period_end=now - timedelta(days=1),  # Period ended
        )
        db_session.add(quota)
        db_session.commit()

        # Check feature quota (which triggers monthly reset check)
        quota_service.check_feature_quota(db_session, test_user.id, "material_upload")

        db_session.refresh(quota)
        # Should have reset monthly counters
        assert quota.material_uploads_used == 0
        assert quota.material_decompositions_used == 0
        assert quota.skill_creates_used == 0
        assert quota.inspiration_copies_used == 0


@pytest.mark.unit
class TestFeatureQuotaMap:
    """Tests for FEATURE_QUOTA_MAP configuration."""

    def test_feature_quota_map_completeness(self):
        """Test that all expected features are in the map."""
        expected_features = [
            "material_upload",
            "material_decompose",
            "skill_create",
            "inspiration_copy",
        ]

        for feature in expected_features:
            assert feature in FEATURE_QUOTA_MAP

    def test_feature_quota_map_field_names(self):
        """Test that mapped field names are valid UsageQuota attributes."""
        for _feature, (_limit_field, used_field) in FEATURE_QUOTA_MAP.items():
            # Verify fields exist in UsageQuota model
            assert hasattr(UsageQuota, used_field), f"Missing field: {used_field}"
