from datetime import datetime, timezone
from sqlalchemy import Boolean, Integer, ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .chat import Chat
from .session import ClaudeSession, MessageChunk
from .user import User
from db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("claude_sessions.id"), nullable=True
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_chunks.id"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    media_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    media_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    chat: Mapped["Chat"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")
    session: Mapped["ClaudeSession | None"] = relationship(
        back_populates="messages", foreign_keys=[session_id]
    )
    chunk: Mapped["MessageChunk | None"] = relationship(
        back_populates="messages", foreign_keys=[chunk_id]
    )

    def __repr__(self):
        return f"<Message(id={self.id}, chat_id={self.chat_id}, is_bot={self.is_bot})>"
