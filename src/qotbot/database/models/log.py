from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from qotbot.database.database import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    level = Column(String(10), nullable=False, index=True)
    logger = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)
    module = Column(String(255), nullable=True)
    function = Column(String(255), nullable=True)
    line = Column(Integer, nullable=True)
    exc_info = Column(Text, nullable=True)

    __table_args__ = (Index("ix_logs_timestamp_level", "timestamp", "level"),)
