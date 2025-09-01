

from dataclasses import dataclass
from datetime import datetime
from typing import List

from models.chat_message import ChatMessage

@dataclass
class Conversation:
    """Represents a conversation thread"""
    conversation_id: str
    chat_id: int
    messages: List[ChatMessage]
    created_at: datetime
    last_activity: datetime

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        self.last_activity = datetime.now()

    def to_dict(self):
        return {
            'conversation_id': self.conversation_id,
            'chat_id': self.chat_id,
            'messages': [msg.to_dict() for msg in self.messages],
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat()
        }