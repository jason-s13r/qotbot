from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship
from qotbot.database.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=True)
    message_date = Column(DateTime, nullable=False)
    is_reply = Column(Boolean, default=False)
    reply_to_message_id = Column(BigInteger, nullable=True)
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    has_image = Column(Boolean, default=False)
    has_audio = Column(Boolean, default=False)
    has_video = Column(Boolean, default=False)
    has_voice = Column(Boolean, default=False)
    image_description = Column(Text, nullable=True)
    audio_transcription = Column(Text, nullable=True)
    poll_results = Column(Text, nullable=True)
    button_options = Column(Text, nullable=True)
    classification_reason = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    audio_transcribed = Column(Boolean, default=False)
    image_transcribed = Column(Boolean, default=False)
    classified = Column(Boolean, default=False)
    responded = Column(Boolean, default=False)
    skip_reason = Column(Text, nullable=True)
    queue_status = Column(String, nullable=True)
    trace_message_id = Column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (PrimaryKeyConstraint("chat_id", "id"),)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    trace_message = relationship("Message", remote_side=[id])
