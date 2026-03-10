from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean
from sqlalchemy.orm import relationship
from qotbot.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_bot = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="sender", foreign_keys="Message.sender_id"
    )
    chats = relationship("ChatMember", back_populates="user")
