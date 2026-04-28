"""
Backward-compatible subscription service import path.

Use `services.subscription.subscription_service` for new code.
"""

from services.subscription.subscription_service import (
    SubscriptionService as _SubscriptionServiceImpl,
)


class SubscriptionService(_SubscriptionServiceImpl):
    """Compatibility alias to the unified subscription service implementation."""

