from typing import Dict, List, Optional
from datetime import datetime
from app.database.models.feedback import Feedback
from app.database.repositories.base_repo import BaseRepository

class FeedbackRepository(BaseRepository):
    """Repository for handling feedback-related database operations."""

    def __init__(self, table_name: str = "feedbacks"):
        super().__init__(table_name)

    async def create_feedback(self, feedback: Feedback) -> str:
        feedback_dict = feedback.model_dump(by_alias=True)
        return await self.insert_one(feedback_dict)

    async def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict]:
        try:
            return await self.find_one({"id": feedback_id})
        except Exception:
            return None

    async def get_feedback_by_user_id(self, user_id: str) -> List[Dict]:
        return await self.find_many({"user_id": user_id}, [("created_at", -1)])

    async def get_all_feedback(self) -> List[Dict]:
        return await self.find_many({}, [("created_at", -1)])

    async def update_feedback(self, feedback_id: str, update_data: Dict) -> bool:
        try:
            update_data["updated_at"] = datetime.now().isoformat()
            return await self.update_one({"id": feedback_id}, update_data)
        except Exception:
            return False

    async def delete_feedback(self, feedback_id: str) -> bool:
        try:
            return await self.delete_one({"id": feedback_id})
        except Exception:
            return False
