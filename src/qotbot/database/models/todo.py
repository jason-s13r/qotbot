import enum
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
    Enum,
)
from sqlalchemy.orm import relationship
from qotbot.database.database import Base


class EditorMode(enum.Enum):
    LIST_OWNER = "list_owner"
    CHAT_ADMIN = "chat_admin"
    CHAT_PARTICIPANTS = "chat_participants"


class TodoList(Base):
    __tablename__ = "todo_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    list_type = Column(String(50), nullable=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    editor_mode = Column(
        Enum(EditorMode), default=EditorMode.LIST_OWNER, nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat = relationship("Chat", back_populates="todo_lists")
    owner = relationship("User", back_populates="owned_todo_lists")
    items = relationship(
        "TodoListItem", back_populates="list", cascade="all, delete-orphan"
    )


class TodoListItem(Base):
    __tablename__ = "todo_list_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    list_id = Column(Integer, ForeignKey("todo_lists.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    list = relationship("TodoList", back_populates="items")
    creator = relationship("User", back_populates="created_todo_items")
