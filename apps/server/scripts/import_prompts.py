"""
Import local prompt configurations to database.

Usage:
    # Import to local database (uses DATABASE_URL)
    python scripts/import_prompts.py

    # Import to specific database
    python scripts/import_prompts.py --db-url "postgresql://user:pass@host:port/db"

    # Force update existing configs
    python scripts/import_prompts.py --force
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlmodel import Session, select

from agent.prompts.novel import NOVEL_PROMPT_CONFIG
from agent.prompts.screenplay import SCREENPLAY_PROMPT_CONFIG
from agent.prompts.short_story import SHORT_STORY_PROMPT_CONFIG
from models import SystemPromptConfig

# Map project types to their local configurations
LOCAL_CONFIGS = {
    "novel": NOVEL_PROMPT_CONFIG,
    "short": SHORT_STORY_PROMPT_CONFIG,
    "screenplay": SCREENPLAY_PROMPT_CONFIG,
}


def import_prompts(db_url: str, force: bool = False):
    """
    Import local prompt configurations to database.

    Args:
        db_url: Database connection URL
        force: If True, update existing configs; if False, skip existing
    """
    print("Connecting to database...")
    engine = create_engine(db_url)

    with Session(engine) as session:
        for project_type, config in LOCAL_CONFIGS.items():
            print(f"\nProcessing: {project_type}")

            # Check if config already exists
            existing = session.exec(
                select(SystemPromptConfig).where(
                    SystemPromptConfig.project_type == project_type
                )
            ).first()

            if existing:
                if force:
                    print("  Updating existing config...")
                    existing.role_definition = config["role_definition"]
                    existing.capabilities = config["capabilities"]
                    existing.directory_structure = config.get("directory_structure")
                    existing.content_structure = config.get("content_structure")
                    existing.file_types = config.get("file_types")
                    existing.writing_guidelines = config.get("writing_guidelines")
                    existing.include_dialogue_guidelines = config.get(
                        "include_dialogue_guidelines", False
                    )
                    existing.primary_content_type = config.get("primary_content_type")
                    existing.is_active = True
                    session.add(existing)
                    print(f"  Updated: {project_type}")
                else:
                    print("  Skipped (already exists, use --force to update)")
            else:
                print("  Creating new config...")
                new_config = SystemPromptConfig(
                    project_type=project_type,
                    role_definition=config["role_definition"],
                    capabilities=config["capabilities"],
                    directory_structure=config.get("directory_structure"),
                    content_structure=config.get("content_structure"),
                    file_types=config.get("file_types"),
                    writing_guidelines=config.get("writing_guidelines"),
                    include_dialogue_guidelines=config.get(
                        "include_dialogue_guidelines", False
                    ),
                    primary_content_type=config.get("primary_content_type"),
                    is_active=True,
                )
                session.add(new_config)
                print(f"  Created: {project_type}")

        session.commit()
        print("\nImport completed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Import local prompt configurations to database"
    )
    parser.add_argument(
        "--db-url",
        help="Database URL (defaults to DATABASE_URL env var)",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update existing configurations",
    )

    args = parser.parse_args()

    # Get database URL
    if args.db_url:
        db_url = args.db_url
    else:
        import os
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("Error: No database URL provided.")
            print("Use --db-url or set DATABASE_URL environment variable.")
            sys.exit(1)

    import_prompts(db_url, args.force)


if __name__ == "__main__":
    main()
