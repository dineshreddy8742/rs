"""Base repository module for database operations using Supabase."""

import re
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.database.connector import SupabaseConnectionManager

class BaseRepository:
    """Base repository class for database operations using Supabase."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.connection_manager = SupabaseConnectionManager()

    def _get_table(self):
        return self.connection_manager.table(self.table_name)

    @staticmethod
    def _get_missing_column_name(error: Exception) -> Optional[str]:
        """Extract a missing column name from a Supabase/PostgREST error."""
        message = str(error)
        match = re.search(r"Could not find the '([^']+)' column", message)
        return match.group(1) if match else None

    async def insert_one(self, data: Dict[str, Any]) -> str:
        """Insert a single record into Supabase with recursive column fallback."""
        payload = dict(data)
        try:
            result = self._get_table().insert(payload).execute()
            if result.data and len(result.data) > 0:
                return str(result.data[0].get("id", ""))
            return ""
        except Exception as e:
            error_msg = str(e)
            print(f"❌ DATABASE INSERT ERROR [{self.table_name}]: {error_msg}")
            
            missing_column = self._get_missing_column_name(e)
            if missing_column and missing_column in payload:
                print(f"⚠️ Column '{missing_column}' missing in {self.table_name}, retrying...")
                retry_payload = {k: v for k, v in payload.items() if k != missing_column}
                return await self.insert_one(retry_payload)
            return ""

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single record in Supabase."""
        try:
            table = self._get_table().select("*")
            for key, value in query.items():
                table = table.eq(key, value)
            
            result = table.limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error finding record in {self.table_name}: {e}")
            return None

    async def find_many(self, query: Dict[str, Any], sort: List = None) -> List[Dict[str, Any]]:
        """Find multiple records in Supabase."""
        try:
            table = self._get_table().select("*")
            for key, value in query.items():
                table = table.eq(key, value)
            
            if sort:
                for field, direction in sort:
                    # direction -1 is DESC, 1 is ASC
                    table = table.order(field, desc=(direction == -1))
            
            result = table.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error finding records in {self.table_name}: {e}")
            return []

    async def update_one(self, query: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Update a single record in Supabase with recursive column fallback."""
        payload = dict(data)
        try:
            table = self._get_table().update(payload)
            for key, value in query.items():
                table = table.eq(key, value)
            result = table.execute()
            return len(result.data) > 0 if result.data else False
        except Exception as e:
            error_msg = str(e)
            print(f"❌ DATABASE UPDATE ERROR [{self.table_name}]: {error_msg}")
            
            missing_column = self._get_missing_column_name(e)
            if missing_column and missing_column in payload:
                print(f"⚠️ Column '{missing_column}' missing in {self.table_name}, retrying update...")
                retry_payload = {k: v for k, v in payload.items() if k != missing_column}
                return await self.update_one(query, retry_payload)
            return False

    async def delete_one(self, query: Dict[str, Any]) -> bool:
        """Delete a single record in Supabase."""
        try:
            # Build the delete query properly
            table = self._get_table().delete()
            
            # Apply filters from query dict
            for key, value in query.items():
                table = table.eq(key, value)

            result = table.execute()
            return len(result.data) > 0 if result.data else False
        except Exception as e:
            print(f"Error deleting record from {self.table_name}: {e}")
            return False

