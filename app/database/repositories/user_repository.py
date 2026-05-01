"""User repository for database operations."""

from typing import Optional, List, Dict
from datetime import datetime
from app.database.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository):
    """Repository for user authentication and management."""

    def __init__(self, table_name: str = "users"):
        super().__init__(table_name)

    def _get_supabase_client(self):
        """Get the underlying Supabase client."""
        return self.connection_manager.get_client()

    async def create_user(self, user_data: Dict) -> Optional[str]:
        """Create a new user. Returns user ID or None if failed."""
        try:
            user_data["created_at"] = datetime.now().isoformat()
            user_data["updated_at"] = datetime.now().isoformat()
            user_data["is_active"] = True
            user_data["is_admin"] = False
            user_data["resume_count"] = 0
            user_data["daily_limit"] = 5
            user_data["monthly_limit"] = 50
            user_data["yearly_limit"] = 500
            
            res = await self.insert_one(user_data)
            return res if res else None
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email (case-insensitive)."""
        try:
            result = self._get_table().select("*").eq("email", email.lower()).execute()
            if result.data:
                user = result.data[0]
                return user
            return None
        except Exception as e:
            print(f"Error finding user by email: {e}")
            return None

    async def get_user_by_roll_number(self, roll_number: str) -> Optional[Dict]:
        """Find user by roll number (case-insensitive)."""
        try:
            result = self._get_table().select("*").eq("roll_number", roll_number.lower()).execute()
            if result.data:
                user = result.data[0]
                if "_id" in user:
                    user["id"] = str(user.pop("_id"))
                return user
            return None
        except Exception as e:
            print(f"Error finding user: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Find user by ID."""
        try:
            result = self._get_table().select("*").eq("id", user_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None

    async def update_user(self, user_id: str, update_data: Dict) -> bool:
        """Update user data with resilient schema handling."""
        try:
            update_data["updated_at"] = datetime.now().isoformat()
            return await self.update_one({"id": user_id}, update_data)
        except Exception as e:
            print(f"🚨 DATABASE UPDATE CRASH: {e}")
            return False

    async def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp."""
        return await self.update_user(user_id, {"last_login": datetime.now().isoformat()})

    async def increment_resume_count(self, user_id: str) -> bool:
        """Increment user's resume count."""
        try:
            user = await self.get_user_by_id(user_id)
            if user:
                current_count = user.get("resume_count", 0)
                return await self.update_user(user_id, {"resume_count": current_count + 1})
            return False
        except Exception:
            return False

    async def increment_download_count(self, user_id: str) -> bool:
        """Increment user's download count."""
        try:
            user = await self.get_user_by_id(user_id)
            if user:
                current_count = user.get("download_count", 0) or 0
                return await self.update_user(user_id, {"download_count": current_count + 1})
            return False
        except Exception:
            return False

    async def get_all_users(self) -> List[Dict]:
        """Get all users (admin only)."""
        try:
            result = self._get_table().select("*").order("created_at", desc=True).execute()
            return result.data or []
        except Exception:
            return []

    async def get_admin_stats(self) -> Dict:
        """Get aggregated statistics for admin dashboard."""
        try:
            users = await self.get_all_users()
            total_users = len(users)
            total_resumes = sum(u.get("resume_count", 0) for u in users)
            colleges = list(set(u.get("college", "Unknown") for u in users))
            
            # Users by college
            users_by_college = {}
            for u in users:
                college = u.get("college", "Unknown")
                users_by_college[college] = users_by_college.get(college, 0) + 1
            
            # Recent logins (last 10)
            recent_logins = sorted(
                [u for u in users if u.get("last_login")],
                key=lambda x: x.get("last_login", ""),
                reverse=True
            )[:10]
            
            return {
                "total_users": total_users,
                "total_resumes": total_resumes,
                "total_downloads": sum(u.get("download_count", 0) or 0 for u in users),
                "colleges": colleges,
                "users_by_college": users_by_college,
                "recent_logins": recent_logins,
            }
        except Exception as e:
            print(f"Error getting admin stats: {e}")
            return {"total_users": 0, "total_resumes": 0, "colleges": [], "users_by_college": {}, "recent_logins": []}

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user (admin only)."""
        try:
            result = self._get_table().delete().eq("id", user_id).execute()
            return len(result.data) > 0 if result.data else False
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False
