from typing import Dict, List, Optional
from datetime import datetime
from app.database.models.feedback import Feedback
from app.database.repositories.base_repo import BaseRepository

class FeedbackRepository(BaseRepository):
    """Repository for handling feedback-related database operations."""

    def __init__(self, table_name: str = "feedback"):
        # Defaulting to "feedback" (singular) as it is more common for this noun
        # and checking both plural/singular if needed could be done in methods
        super().__init__(table_name)

    async def create_feedback(self, feedback: Feedback) -> tuple[str, Optional[str]]:
        feedback_dict = feedback.model_dump(by_alias=True)
        # Resilient insert with local name override
        current_table = self.table_name
        res_id, error = await self.insert_one(feedback_dict)

        if not res_id and current_table == "feedback":
            # Fallback to "feedbacks" if singular fails
            print("⚠️ Singular 'feedback' table insert failed, retrying with plural 'feedbacks'...")
            self.table_name = "feedbacks"
            res_id, error = await self.insert_one(feedback_dict)

        return res_id, error


    async def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict]:
        try:
            return await self.find_one({"id": feedback_id})
        except Exception:
            return None

    async def get_feedback_by_user_id(self, user_id: str) -> List[Dict]:
        try:
            return await self.find_many({"user_id": user_id}, [("created_at", -1)])
        except Exception:
            # Fallback without sort if created_at is missing
            return await self.find_many({"user_id": user_id})

    async def get_all_feedback(self) -> List[Dict]:
        try:
            items = await self.find_many({}, [("created_at", -1)])
            if not items:
                # If nothing found, try the other variant
                other_table = "feedbacks" if self.table_name == "feedback" else "feedback"
                print(f"🔍 No feedback in '{self.table_name}', checking '{other_table}'...")
                original_table = self.table_name
                self.table_name = other_table
                items = await self.find_many({}, [("created_at", -1)])
                if not items:
                    # Fallback without sort
                    items = await self.find_many({})
                    if not items:
                        # If still nothing, revert to avoid side effects
                        self.table_name = original_table
            return items
        except Exception:
            # Fallback without sort
            return await self.find_many({})
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
