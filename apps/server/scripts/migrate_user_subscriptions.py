"""
Data Migration Script - Create free tier subscriptions for existing users.

Usage:
    python scripts/migrate_user_subscriptions.py [--dry-run] [--force]

Options:
    --dry-run    Preview changes without applying
    --force      Skip confirmation prompt
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from sqlmodel import Session, select

from database import sync_engine
from models.entities import User
from models.subscription import SubscriptionHistory, SubscriptionPlan, UsageQuota, UserSubscription


def migrate_users(dry_run: bool = False):
    """Migrate existing users to free tier subscriptions."""
    with Session(sync_engine) as session:
        # Get free plan
        free_plan = session.exec(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
        ).first()

        if not free_plan:
            print("ERROR: Free plan not found. Run seed_subscription_plans.py first.")
            return

        # Find users without subscriptions
        existing_sub_user_ids = session.exec(
            select(UserSubscription.user_id)
        ).all()

        users_without_sub = session.exec(
            select(User).where(~User.id.in_(existing_sub_user_ids))
        ).all()

        print(f"Found {len(users_without_sub)} users without subscriptions")

        if dry_run:
            print("[DRY RUN] Would create subscriptions for:")
            for user in users_without_sub:
                print(f"  - {user.username} ({user.email})")
            return

        now = datetime.utcnow()
        created = 0

        for user in users_without_sub:
            try:
                # Create subscription
                subscription = UserSubscription(
                    user_id=user.id,
                    plan_id=free_plan.id,
                    status="active",
                    current_period_start=now,
                    current_period_end=now + timedelta(days=36500),  # ~100 years
                )
                session.add(subscription)

                # Create quota
                quota = UsageQuota(
                    user_id=user.id,
                    period_start=now,
                    period_end=now + timedelta(days=30),
                    ai_conversations_used=0,
                    last_reset_at=now,
                )
                session.add(quota)

                # Create history
                history = SubscriptionHistory(
                    user_id=user.id,
                    action="migrated",
                    plan_name="free",
                    start_date=now,
                    event_metadata={"source": "data_migration", "script": "migrate_user_subscriptions.py"}
                )
                session.add(history)

                created += 1
                print(f"  Created subscription for {user.username}")

            except Exception as e:
                print(f"  ERROR for {user.username}: {e}")
                continue

        if created > 0:
            session.commit()
            print(f"\nSuccessfully migrated {created} users to free tier")
        else:
            print("\nNo users needed migration")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    if not force and not dry_run:
        confirm = input("This will create subscriptions for existing users. Continue? [y/N] ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    migrate_users(dry_run=dry_run)
