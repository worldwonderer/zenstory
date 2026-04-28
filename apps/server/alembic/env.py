"""
Alembic Environment Configuration for zenstory
===========================================

This file is part of the Alembic migration environment configuration.
It handles the setup of database connections and model metadata for migrations.
"""

from logging.config import fileConfig

from sqlalchemy import inspect, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from alembic import context

# Import your models and metadata
from database import DATABASE_URL

# Import all models to ensure they are registered with SQLModel.metadata
from models import Inspiration  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

# Override sqlalchemy.url with environment variable if set
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


ALEMBIC_VERSION_COLUMN_LENGTH = 128


def _ensure_alembic_version_column_capacity(connection: Connection) -> None:
    """
    Ensure alembic_version.version_num can store long revision identifiers.

    Alembic defaults this column to VARCHAR(32), but this project uses timestamp
    + descriptive revision IDs that can exceed 32 characters.
    """
    inspector = inspect(connection)
    if not inspector.has_table("alembic_version"):
        connection.execute(
            text(
                f"""
                CREATE TABLE alembic_version (
                    version_num VARCHAR({ALEMBIC_VERSION_COLUMN_LENGTH}) NOT NULL PRIMARY KEY
                )
                """
            )
        )
        return

    columns = {column["name"]: column for column in inspector.get_columns("alembic_version")}
    version_column = columns.get("version_num")
    if not version_column:
        return

    current_length = getattr(version_column.get("type"), "length", None)
    if current_length is None or current_length >= ALEMBIC_VERSION_COLUMN_LENGTH:
        return

    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                f"""
                ALTER TABLE alembic_version
                ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_COLUMN_LENGTH})
                """
            )
        )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a given connection."""
    _ensure_alembic_version_column_capacity(connection)
    if connection.in_transaction():
        connection.commit()
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode for PostgreSQL."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Use sync migrations for all databases (psycopg2 for PostgreSQL)
    from sqlalchemy import create_engine

    database_url = config.get_main_option("sqlalchemy.url") or DATABASE_URL

    # Convert async URL to sync URL if needed
    if database_url and "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
