from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    BigInteger,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship
from qotbot.database.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=True)
    chat_type = Column(String, nullable=False)
    username = Column(String, nullable=True)
    overall_summary = Column(Text, nullable=True)
    daily_summary_path = Column(String, nullable=True)
    can_respond = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="chat", foreign_keys="Message.chat_id"
    )
    members = relationship("ChatMember", back_populates="chat")
    rules = relationship("Rule", back_populates="chat", cascade="all, delete-orphan")
    todo_lists = relationship("TodoList", back_populates="chat")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chats")
    chat = relationship("Chat", back_populates="members")
