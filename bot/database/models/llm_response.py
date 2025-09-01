from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class LLMResponse(Base):
    __tablename__ = 'llm_responses'
    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey('messages.id'))
    thinking_text = Column(Text)
    response_text = Column(Text)
    tool_use = Column(JSON)
    duration = Column(Float)
    model = Column(String)
    created_at = Column(DateTime)
    metadata = Column(JSON)
