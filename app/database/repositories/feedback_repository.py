"""Feedback repository module for database operations."""

from datetime import datetime
from typing import Dict, List, Optional

from app.database.models.feedback import Feedback, FeedbackMessage
from app.database.repositories.base_repo import BaseRepository


class FeedbackRepository(BaseRepository):
    """Repository for handling feedback-related database operations."""

    def __init__(self, table_name: str = "feedback"):
        """Initialize the feedback repository."""
        super().__init__(table_name)

    async def create_feedback(self, feedback: Feedback) -> str:
        """Create a new feedback record."""
        feedback_dict = feedback.model_dump(by_alias=True)
        return await self.insert_one(feedback_dict)

    async def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict]:
        """Retrieve feedback by its ID."""
        try:
            return await self.find_one({"id": feedback_id})
        except Exception:
            return None

    async def get_user_feedback(self, user_id: str) -> List[Dict]:
        """Retrieve all feedback from a specific user."""
        return await self.find_many({"user_id": user_id}, [("created_at", -1)])

    async def get_all_feedback(self) -> List[Dict]:
        """Retrieve all feedback for admins."""
        return await self.find_many({}, [("created_at", -1)])

    async def update_feedback(self, feedback_id: str, update_data: Dict) -> bool:
        """Update feedback metadata (rating, status, etc.)."""
        try:
            update_data["updated_at"] = datetime.now().isoformat()
            return await self.update_one({"id": feedback_id}, update_data)
        except Exception:
            return False

    async def add_message(self, feedback_id: str, message: FeedbackMessage) -> bool:
        """Add a message to the feedback thread."""
        try:
            feedback = await self.get_feedback_by_id(feedback_id)
            if not feedback:
                return False
            
            messages = feedback.get("messages", [])
            messages.append(message.model_dump())
            
            return await self.update_one(
                {"id": feedback_id},
                {
                    "messages": messages,
                    "updated_at": datetime.now().isoformat()
                }
            )
        except Exception:
            return False

    async def mark_messages_as_read(self, feedback_id: str, current_user_role: str) -> bool:
        """Mark all messages from the other side as read."""
        try:
            feedback = await self.get_feedback_by_id(feedback_id)
            if not feedback:
                return False
            
            messages = feedback.get("messages", [])
            modified = False
            for msg in messages:
                if msg.get("sender_role") != current_user_role and not msg.get("is_read"):
                    msg["is_read"] = True
                    modified = True
            
            if not modified:
                return True
                
            return await self.update_one(
                {"id": feedback_id},
                {
                    "messages": messages,
                    "updated_at": datetime.now().isoformat()
                }
            )
        except Exception:
            return False

    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete a feedback record."""
        try:
            return await self.delete_one({"id": feedback_id})
        except Exception:
            return False
