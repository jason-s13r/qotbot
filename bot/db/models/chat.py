from datetime import datetime, timezone
from sqlalchemy import Integer, BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    permission: Mapped[str] = mapped_column(String, default="none", nullable=False)
    throttle_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["ClaudeSession"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["MessageChunk"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Chat(telegram_id={self.telegram_id}, permission={self.permission})>"
