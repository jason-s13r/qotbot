

import json
from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, Optional

from models.conversation import Conversation
from models.chat_message import ChatMessage

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation storage and retrieval"""

    def __init__(self, data_path: Path):
        self.storage_path = data_path / "conversations.json"
        self.conversations: Dict[str, Conversation] = {}
        self.message_to_conversation: Dict[int, str] = {}
        self._load_conversations()

    def _load_conversations(self):
        """Load conversations from storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for conv_data in data.get('conversations', []):
                        conv = Conversation(
                            conversation_id=conv_data['conversation_id'],
                            chat_id=conv_data['chat_id'],
                            messages=[
                                ChatMessage(
                                    role=msg['role'],
                                    content=msg['content'],
                                    timestamp=datetime.fromisoformat(msg['timestamp']),
                                    telegram_message_id=msg['telegram_message_id'],
                                    name=msg["name"]
                                ) for msg in conv_data['messages']
                            ],
                            created_at=datetime.fromisoformat(conv_data['created_at']),
                            last_activity=datetime.fromisoformat(conv_data['last_activity'])
                        )
                        self.conversations[conv.conversation_id] = conv

                        # Rebuild message to conversation mapping
                        for msg in conv.messages:
                            self.message_to_conversation[msg.telegram_message_id] = conv.conversation_id

            except Exception as e:
                logger.error(f"Error loading conversations: {e}")

    def _save_conversations(self):
        """Save conversations to storage"""
        try:
            data = {
                'conversations': [conv.to_dict() for conv in self.conversations.values()]
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversations: {e}")

    def create_conversation(self, chat_id: int, initial_message_id: int) -> str:
        """Create a new conversation"""
        conversation_id = f"{chat_id}_{datetime.now().timestamp()}"
        conv = Conversation(
            conversation_id=conversation_id,
            chat_id=chat_id,
            messages=[],
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        self.conversations[conversation_id] = conv
        self.message_to_conversation[initial_message_id] = conversation_id
        self._save_conversations()
        return conversation_id

    def get_conversation_by_message_id(self, message_id: int) -> Optional[Conversation]:
        """Get conversation by telegram message ID"""
        conv_id = self.message_to_conversation.get(message_id)
        if conv_id:
            return self.conversations.get(conv_id)
        return None

    def add_message_to_conversation(self, conversation_id: str, message: ChatMessage):
        """Add a message to a conversation"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].add_message(message)
            self.message_to_conversation[message.telegram_message_id] = conversation_id
            self._save_conversations()