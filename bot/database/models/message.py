from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    id = Column(String, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    chat_id = Column(String, ForeignKey('channels.telegram_id'))
    sender_id = Column(String, ForeignKey('users.telegram_id'))
    content = Column(Text)
    sent_by_bot = Column(Boolean)
    timestamp = Column(DateTime)
