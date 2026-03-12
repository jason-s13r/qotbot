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


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=True)
    message_date = Column(DateTime, nullable=False)
    is_reply = Column(Boolean, default=False)
    reply_to_message_id = Column(BigInteger, nullable=True)
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    image_description = Column(Text, nullable=True)
    audio_transcription = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="messages")
