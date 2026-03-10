from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ClaudeSession(Base):
    __tablename__ = "claude_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    trigger_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chat: Mapped["Chat"] = relationship(back_populates="sessions")
    trigger_message: Mapped["Message"] = relationship(
        foreign_keys=[trigger_message_id], post_update=True
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", foreign_keys="Message.session_id"
    )

    def __repr__(self):
        return f"<ClaudeSession(id={self.id}, status={self.status})>"


class MessageChunk(Base):
    __tablename__ = "message_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_start: Mapped[int] = mapped_column(Integer, nullable=False)
    message_end: Mapped[int] = mapped_column(Integer, nullable=False)
    summarized_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    chat: Mapped["Chat"] = relationship(back_populates="chunks")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chunk", foreign_keys="Message.chunk_id"
    )

    def __repr__(self):
        return f"<MessageChunk(id={self.id}, chunk_index={self.chunk_index})>"


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="memories")

    def __repr__(self):
        return f"<Memory(id={self.id}, user_id={self.user_id})>"
