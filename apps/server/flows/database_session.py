"""
数据库会话管理

提供 Prefect 任务中使用的数据库会话上下文管理器
"""
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlmodel import Session

# 加载 .env 文件（Prefect worker 不会自动加载）
load_dotenv()

# 创建专用于 Prefect flows 的数据库引擎
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zenstory.db")
is_postgres = DATABASE_URL.startswith("postgresql")

if is_postgres:
    # PostgreSQL - use psycopg3 (psycopg) driver
    pg_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    _prefect_engine = create_engine(pg_url, pool_size=5, max_overflow=0)
else:
    # SQLite with WAL mode and timeout for better concurrency
    _prefect_engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
        pool_pre_ping=True,
    )

    @event.listens_for(_prefect_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


@contextmanager
def get_prefect_db_session():
    """为 Prefect flows 提供数据库会话"""
    with Session(_prefect_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# 别名，兼容旧代码
get_db_session = get_prefect_db_session
