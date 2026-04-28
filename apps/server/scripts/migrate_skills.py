"""
Migrate builtin skills to remote PostgreSQL database.

Usage:
    # Migrate to specific database
    python scripts/migrate_skills.py --db-url "postgresql://user:pass@host:port/db"

    # Force update existing skills
    python scripts/migrate_skills.py --db-url "..." --force
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlmodel import Session, select

from agent.skills.loader import load_builtin_skills
from models import PublicSkill

# Category mapping for builtin skills
SKILL_CATEGORIES = {
    "continue-writing": "writing",
    "create-character": "character",
    "create-outline": "plot",
    "describe-scene": "writing",
    "design-conflict": "plot",
    "generate-dialogue": "writing",
    "generate-opening": "writing",
    "hook-design": "plot",
    "immersion-enhance": "style",
    "polish-text": "style",
    "reversal-design": "plot",
    "rhythm-control": "style",
    "worldbuilding": "worldbuilding",
}


def migrate_skills(db_url: str, force: bool = False):
    """
    Migrate builtin skills to database as public skills.

    Args:
        db_url: Database connection URL
        force: If True, update existing skills; if False, skip existing
    """
    print("Loading builtin skills from markdown files...")
    builtin_skills = load_builtin_skills()
    print(f"Found {len(builtin_skills)} builtin skills")

    print("\nConnecting to database...")
    engine = create_engine(db_url)

    with Session(engine) as session:
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for skill in builtin_skills:
            print(f"\nProcessing: {skill.name} (id: {skill.id})")

            # Check if skill already exists by name
            existing = session.exec(
                select(PublicSkill).where(PublicSkill.name == skill.name)
            ).first()

            category = SKILL_CATEGORIES.get(skill.id, "writing")

            if existing:
                if force:
                    print("  Updating existing skill...")
                    existing.description = skill.description
                    existing.instructions = skill.instructions
                    existing.category = category
                    existing.tags = json.dumps(skill.triggers)
                    existing.source = "official"
                    existing.status = "approved"
                    session.add(existing)
                    updated_count += 1
                    print(f"  Updated: {skill.name}")
                else:
                    skipped_count += 1
                    print("  Skipped (already exists, use --force to update)")
            else:
                print("  Creating new public skill...")
                new_skill = PublicSkill(
                    name=skill.name,
                    description=skill.description,
                    instructions=skill.instructions,
                    category=category,
                    tags=json.dumps(skill.triggers),
                    source="official",
                    status="approved",
                    add_count=0,
                )
                session.add(new_skill)
                created_count += 1
                print(f"  Created: {skill.name}")

        session.commit()

        print("\n" + "=" * 50)
        print("Migration completed!")
        print(f"  Created: {created_count}")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped: {skipped_count}")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate builtin skills to database"
    )
    parser.add_argument(
        "--db-url",
        required=True,
        help="Database URL (PostgreSQL connection string)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update existing skills",
    )

    args = parser.parse_args()
    migrate_skills(args.db_url, args.force)


if __name__ == "__main__":
    main()
