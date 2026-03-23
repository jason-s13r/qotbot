from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base
import logging

from qotbot.utils.config import DATABASE_PATH, LOGS_DB_PATH

logger = logging.getLogger(__name__)

Base = declarative_base()

_main_db_engine = None
_main_db_async_session = None
_log_db_engine = None
_log_db_async_session = None


def _create_async_engine(db_path: Path):
    return create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )


def _create_db_session(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _sync_database_schema_sync(database_path):
    """Synchronous schema sync using sync engine."""
    sync_engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(sync_engine)
    existing_tables = inspector.get_table_names()

    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            table.create(sync_engine)
        else:
            existing_columns = {
                col["name"] for col in inspector.get_columns(table.name)
            }
            model_columns = {col.name for col in table.columns}

            for column_name in model_columns - existing_columns:
                column = table.columns[column_name]
                with sync_engine.begin() as conn:
                    conn.execute(
                        text(
                            f'ALTER TABLE {table.name} ADD COLUMN "{column_name}" '
                            f"{column.type} "
                            f"{'NOT NULL' if not column.nullable else ''} "
                            f"{'DEFAULT ' + str(column.default.arg) if column.default is not None else ''}"
                        )
                    )

    sync_engine.dispose()


async def _sync_database_schema(database_path):
    try:
        import asyncio

        await asyncio.to_thread(_sync_database_schema_sync, database_path)
    except Exception as e:
        raise Exception(f"Failed to sync database schema: {str(e)}")


async def init_db(database_path):
    database_path = Path(database_path)
    logger.info(f"Initializing database at {database_path}")

    database_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Syncing database schema")
    await _sync_database_schema(database_path)
    logger.info("Database schema synced")

    logger.info("Creating database engine")
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        echo=False,
    )

    logger.info("Creating async session factory")
    async_session = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    logger.info("Database initialization complete")
    return async_session


def get_database():
    """Get or create the main database engine and session factory."""
    global _main_db_engine, _main_db_async_session
    if _main_db_engine is None:
        _main_db_engine = _create_async_engine(DATABASE_PATH)
        _main_db_async_session = _create_db_session(_main_db_engine)
    return _main_db_async_session


def get_log_database():
    """Get or create the log database engine and session factory."""
    global _log_db_engine, _log_db_async_session
    if _log_db_engine is None:
        _log_db_engine = _create_async_engine(LOGS_DB_PATH)
        _log_db_async_session = _create_db_session(_log_db_engine)
    return _log_db_async_session


@asynccontextmanager
async def get_log_session():
    """Get a database session. Uses cached engine if database_path is None."""
    async_session = get_log_database()

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session():
    """Get a database session. Uses cached engine if database_path is None."""
    async_session = get_database()
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
