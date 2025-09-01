from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(String, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    type = Column(String)
    created_at = Column(DateTime)
