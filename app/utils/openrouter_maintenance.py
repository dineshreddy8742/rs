import httpx
import logging
import asyncio
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class OpenRouterMaintenance:
    """Utility for autonomously maintaining and re-enabling OpenRouter API keys."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self):
        self.mgmt_key = settings.OPENROUTER_MANAGEMENT_KEY
        self.headers = {
            "Authorization": f"Bearer {self.mgmt_key}",
            "Content-Type": "application/json"
        }

    async def get_all_keys(self) -> List[Dict[str, Any]]:
        """Fetch all keys associated with the account using the management key."""
        if not self.mgmt_key:
            logger.warning("No OpenRouter Management Key found in settings.")
            return []
            
        async with httpx.AsyncClient() as client:
            try:
                # Note: The endpoint might be /keys according to search results
                response = await client.get(f"{self.BASE_URL}/keys", headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"Failed to fetch keys: {response.status_code} - {response.text}")
                    return []
            except Exception as e:
                logger.error(f"Error fetching OpenRouter keys: {e}")
                return []

    async def re_enable_key(self, key_hash: str) -> bool:
        """Re-enable a specific key by its hash."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.BASE_URL}/keys/{key_hash}",
                    headers=self.headers,
                    json={"disabled": False}
                )
                if response.status_code == 200:
                    logger.info(f"Successfully re-enabled OpenRouter key hash: {key_hash}")
                    return True
                else:
                    logger.error(f"Failed to re-enable key {key_hash}: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error re-enabling key {key_hash}: {e}")
                return False

    async def run_maintenance(self):
        """Scan all keys and re-enable any that are disabled."""
        logger.info("Starting OpenRouter Key Maintenance Protocol...")
        keys = await self.get_all_keys()
        
        disabled_count = 0
        for key in keys:
            if key.get("disabled") is True:
                logger.warning(f"Detected disabled key: {key.get('name')} (Hash: {key.get('id')})")
                success = await self.re_enable_key(key.get("id"))
                if success:
                    disabled_count += 1

        if disabled_count > 0:
            logger.info(f"Maintenance complete. {disabled_count} keys were resurrected.")
        else:
            logger.info("Maintenance complete. All keys are already in active state.")
            
        return disabled_count

# Background maintenance task
async def start_self_healing_service(interval_seconds: int = 300):
    """Background loop that periodically checks and heals keys."""
    maintenance = OpenRouterMaintenance()
    while True:
        try:
            await maintenance.run_maintenance()
        except Exception as e:
            logger.error(f"Self-healing service error: {e}")
        await asyncio.sleep(interval_seconds)
