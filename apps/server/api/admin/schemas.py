"""
Shared Pydantic models for Admin API endpoints.

This module contains all request and response schemas used across
the admin API modules.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ==================== User Management Schemas ====================


class UserUpdateRequest(BaseModel):
    """Request body for updating a user"""
    username: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None


# ==================== System Prompt Management Schemas ====================


class SystemPromptConfigRequest(BaseModel):
    """Request body for creating or updating system prompt configuration"""
    role_definition: str
    capabilities: str
    directory_structure: str | None = None
    content_structure: str | None = None
    file_types: str | None = None
    writing_guidelines: str | None = None
    include_dialogue_guidelines: bool | None = False
    primary_content_type: str | None = None
    is_active: bool | None = True


# ==================== Skill Review Schemas ====================


class SkillReviewRequest(BaseModel):
    """Request body for reviewing a skill"""
    rejection_reason: str | None = None


class PendingSkillResponse(BaseModel):
    """Response model for pending skill"""
    id: str
    name: str
    description: str | None
    instructions: str
    category: str
    author_id: str | None
    author_name: str | None = None
    created_at: datetime


# ==================== Inspiration Management Schemas ====================


class CreateInspirationRequest(BaseModel):
    """Request body for creating an inspiration from a project"""
    project_id: str
    name: str | None = None
    description: str | None = None
    cover_image: str | None = None
    tags: list[str] | None = None
    source: str = "official"
    is_featured: bool = False


class InspirationReviewRequest(BaseModel):
    """Request body for reviewing an inspiration"""
    approve: bool
    # Required when approve=False
    rejection_reason: str | None = None


class UpdateInspirationRequest(BaseModel):
    """Request body for updating an inspiration"""
    name: str | None = None
    description: str | None = None
    cover_image: str | None = None
    tags: list[str] | None = None
    is_featured: bool | None = None
    sort_order: int | None = None
    status: Literal["pending", "approved", "rejected"] | None = None


# ==================== Feedback Management Schemas ====================


class FeedbackStatusUpdateRequest(BaseModel):
    """Request body for updating feedback status."""

    status: Literal["open", "processing", "resolved"]


# ==================== Subscription Plan Schemas ====================


class PlanUpdateRequest(BaseModel):
    """Request body for updating a subscription plan"""
    display_name: str | None = None
    display_name_en: str | None = None
    price_monthly_cents: int | None = None
    price_yearly_cents: int | None = None
    features: dict | None = None
    is_active: bool | None = None


# ==================== Redemption Code Schemas ====================


class CodeCreateRequest(BaseModel):
    """Request body for creating a redemption code"""
    tier: str = Field(..., min_length=2, max_length=32)
    duration_days: int = Field(..., ge=1, le=36500)
    code_type: Literal["single_use", "multi_use", "single", "multi"] = "single_use"
    max_uses: int | None = Field(default=None, ge=1, le=100000)
    notes: str | None = Field(default=None, max_length=500)


class CodeBatchCreateRequest(BaseModel):
    """Request body for batch creating redemption codes"""
    tier: str = Field(..., min_length=2, max_length=32)
    duration_days: int = Field(..., ge=1, le=36500)
    count: int = Field(..., ge=1, le=100)
    code_type: Literal["single_use", "multi_use", "single", "multi"] = "single_use"
    notes: str | None = Field(default=None, max_length=500)


class CodeUpdateRequest(BaseModel):
    """Request body for updating a redemption code"""
    is_active: bool | None = None
    notes: str | None = None


class CodeListResponse(BaseModel):
    """Response model for code list"""
    items: list
    total: int
    page: int
    page_size: int


# ==================== Subscription Management Schemas ====================


class SubscriptionUpdateRequest(BaseModel):
    """Request body for updating a subscription"""
    plan_name: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=36500)
    status: Literal["active", "expired", "past_due", "cancelled", "canceled"] | None = None


class SubscriptionListResponse(BaseModel):
    """Response model for subscription list"""
    items: list
    total: int
    page: int
    page_size: int


# ==================== Dashboard Schemas ====================


class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics"""
    total_users: int
    active_users: int
    new_users_today: int
    total_projects: int
    total_inspirations: int
    pending_inspirations: int
    active_subscriptions: int
    pro_users: int
    # Commercialization stats
    total_points_in_circulation: int
    today_check_ins: int
    active_invite_codes: int
    week_referrals: int


class ActivationFunnelStepResponse(BaseModel):
    """Single activation funnel step."""

    event_name: str
    label: str
    users: int
    conversion_from_previous: float | None = None
    drop_off_from_previous: int | None = None


class ActivationFunnelResponse(BaseModel):
    """Activation funnel response for admin dashboard."""

    window_days: int
    period_start: str
    period_end: str
    steps: list[ActivationFunnelStepResponse]
    activation_rate: float


class UpgradeConversionSourceResponse(BaseModel):
    """Per-source upgrade conversion statistics."""

    source: str
    conversions: int
    share: float


class UpgradeConversionStatsResponse(BaseModel):
    """Upgrade conversion attribution stats for admin dashboard."""

    window_days: int
    period_start: str
    period_end: str
    total_conversions: int
    unattributed_conversions: int
    sources: list[UpgradeConversionSourceResponse]


class UpgradeFunnelTotalsResponse(BaseModel):
    """Upgrade funnel totals across all sources."""

    expose: int
    click: int
    conversion: int


class UpgradeFunnelSourceResponse(BaseModel):
    """Per-source upgrade funnel stats."""

    source: str
    exposes: int
    clicks: int
    conversions: int
    click_through_rate: float
    conversion_rate_from_click: float
    conversion_rate_from_expose: float


class UpgradeFunnelStatsResponse(BaseModel):
    """Upgrade funnel overview for admin dashboard."""

    window_days: int
    period_start: str
    period_end: str
    totals: UpgradeFunnelTotalsResponse
    sources: list[UpgradeFunnelSourceResponse]


# ==================== Audit Log Schemas ====================


class AuditLogListResponse(BaseModel):
    """Response model for audit log list"""
    items: list
    page: int
    page_size: int


# ==================== Points Management Schemas ====================


class AdminPointsBalance(BaseModel):
    """User points details for admin"""
    user_id: str
    username: str
    email: str
    available: int
    pending_expiration: int
    total_earned: int
    total_spent: int


class AdminPointsAdjustRequest(BaseModel):
    """Points adjustment request"""
    amount: int  # Positive to add, negative to deduct
    reason: str  # Adjustment reason


class PointsStatsResponse(BaseModel):
    """Points system statistics"""
    total_points_issued: int
    total_points_spent: int
    total_points_expired: int
    active_users_with_points: int


class PointsTransactionListResponse(BaseModel):
    """Response model for points transactions list"""
    items: list
    total: int
    page: int
    page_size: int


# ==================== Check-in Stats Schemas ====================


class CheckInStatsResponse(BaseModel):
    """Check-in statistics"""
    today_count: int
    yesterday_count: int
    week_total: int
    streak_distribution: dict  # {7: 10, 14: 5, 30: 2}


class CheckInRecordResponse(BaseModel):
    """Check-in record response"""
    id: str
    user_id: str
    username: str
    check_in_date: date
    streak_days: int
    points_earned: int
    created_at: datetime


class CheckInRecordListResponse(BaseModel):
    """Response model for check-in records list"""
    items: list[CheckInRecordResponse]
    total: int
    page: int
    page_size: int


# ==================== Referral Management Schemas ====================


class AdminReferralStatsResponse(BaseModel):
    """Referral system statistics"""
    total_codes: int
    active_codes: int
    total_referrals: int
    successful_referrals: int
    pending_rewards: int
    total_points_awarded: int


class AdminInviteCodeResponse(BaseModel):
    """Invite code details"""
    id: str
    code: str
    owner_id: str
    owner_name: str
    max_uses: int
    current_uses: int
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


class InviteCodeListResponse(BaseModel):
    """Response model for invite codes list"""
    items: list[AdminInviteCodeResponse]
    total: int
    page: int
    page_size: int


class ReferralRewardListResponse(BaseModel):
    """Response model for referral rewards list"""
    items: list
    total: int
    page: int
    page_size: int


# ==================== Quota Usage Schemas ====================


class QuotaUsageStatsResponse(BaseModel):
    """Quota usage statistics"""
    material_uploads: int
    material_decomposes: int
    skill_creates: int
    inspiration_copies: int


class UserQuotaDetail(BaseModel):
    """User quota details"""
    user_id: str
    username: str
    plan_name: str
    ai_conversations_used: int
    ai_conversations_limit: int
    material_upload_used: int
    material_upload_limit: int
    skill_create_used: int
    skill_create_limit: int
    inspiration_copy_used: int
    inspiration_copy_limit: int
