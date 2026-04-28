"""
Seed script for subscription plans.

Usage:
    python scripts/seed_subscription_plans.py [--force]

Options:
    --force    Overwrite existing plans
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select

from database import sync_engine
from models.subscription import SubscriptionPlan

FREE_PLAN_FEATURES = {
    "ai_conversations_per_day": 20,
    "context_window_tokens": 4096,
    "file_versions_per_file": 10,
    "max_projects": 3,
    "export_formats": ["txt"],
    "custom_prompts": False,
    "materials_library_access": False,
    "material_uploads": 0,
    "material_decompositions": 0,
}

PRO_PLAN_FEATURES = {
    "ai_conversations_per_day": -1,  # Unlimited
    "context_window_tokens": 16384,
    "file_versions_per_file": 100,
    "max_projects": -1,  # Unlimited
    "export_formats": ["txt"],
    "custom_prompts": True,
    "materials_library_access": True,
    "material_uploads": 5,
    "material_decompositions": 5,
}

def seed_plans(force: bool = False):
    """Seed subscription plans."""
    with Session(sync_engine) as session:
        # Check existing plans
        existing = session.exec(select(SubscriptionPlan)).all()
        existing_names = {p.name for p in existing}

        plans_to_create = []

        # Handle free plan
        if "free" not in existing_names:
            free_plan = SubscriptionPlan(
                name="free",
                display_name="免费版",
                display_name_en="Free",
                price_monthly_cents=0,
                price_yearly_cents=0,
                features=FREE_PLAN_FEATURES,
                is_active=True
            )
            plans_to_create.append(free_plan)
        elif force:
            # Delete old and create new
            old = session.exec(select(SubscriptionPlan).where(SubscriptionPlan.name == "free")).first()
            if old:
                session.delete(old)
                session.flush()  # Flush delete before insert
            free_plan = SubscriptionPlan(
                name="free",
                display_name="免费版",
                display_name_en="Free",
                price_monthly_cents=0,
                price_yearly_cents=0,
                features=FREE_PLAN_FEATURES,
                is_active=True
            )
            plans_to_create.append(free_plan)

        # Handle pro plan
        if "pro" not in existing_names:
            pro_plan = SubscriptionPlan(
                name="pro",
                display_name="专业版",
                display_name_en="Pro",
                price_monthly_cents=4900,  # 49 CNY
                price_yearly_cents=39900,  # 399 CNY
                features=PRO_PLAN_FEATURES,
                is_active=True
            )
            plans_to_create.append(pro_plan)
        elif force:
            # Delete old and create new
            old = session.exec(select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")).first()
            if old:
                session.delete(old)
                session.flush()  # Flush delete before insert
            pro_plan = SubscriptionPlan(
                name="pro",
                display_name="专业版",
                display_name_en="Pro",
                price_monthly_cents=4900,  # 49 CNY
                price_yearly_cents=39900,  # 399 CNY
                features=PRO_PLAN_FEATURES,
                is_active=True
            )
            plans_to_create.append(pro_plan)

        if plans_to_create:
            for plan in plans_to_create:
                session.add(plan)
            session.commit()
            print(f"Created {len(plans_to_create)} plans: {[p.name for p in plans_to_create]}")
        else:
            print("All plans already exist. Use --force to overwrite.")

if __name__ == "__main__":
    force = "--force" in sys.argv
    seed_plans(force)
