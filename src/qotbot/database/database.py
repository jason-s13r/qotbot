from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


def _sync_database_schema(engine):
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                table.create(engine)
            else:
                existing_columns = {
                    col["name"] for col in inspector.get_columns(table.name)
                }
                model_columns = {col.name for col in table.columns}

                for column_name in model_columns - existing_columns:
                    column = table.columns[column_name]
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                f'ALTER TABLE {table.name} ADD COLUMN "{column_name}" '
                                f"{column.type} "
                                f"{'NOT NULL' if not column.nullable else ''} "
                                f"{'DEFAULT ' + str(column.default.arg) if column.default is not None else ''}"
                            )
                        )
    except Exception as e:
        raise Exception(f"Failed to sync database schema: {str(e)}")


def init_db(database_path):
    database_path = Path(database_path)
    logger.info(f"Initializing database at {database_path}")

    database_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Creating database engine")
    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    logger.info("Syncing database schema")
    _sync_database_schema(engine)
    logger.info("Database schema synced")

    logger.info("Creating session factory")
    Session = sessionmaker(bind=engine)
    logger.info("Database initialization complete")
    return Session()


@contextmanager
def get_session(database_path):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
