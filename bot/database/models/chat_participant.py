from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ChatParticipant(Base):
    __tablename__ = 'chat_participants'
    id = Column(String, primary_key=True)
    chat_id = Column(String, ForeignKey('channels.telegram_id'))
    user_id = Column(String, ForeignKey('users.telegram_id'))
    joined_at = Column(DateTime)
    role = Column(String)
