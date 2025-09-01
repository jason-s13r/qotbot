from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """Represents a message in a conversation"""
    role: str
    content: str
    timestamp: datetime
    telegram_message_id: int
    name: str

    def to_dict(self):
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'telegram_message_id': self.telegram_message_id,
            "name": self.name
        }