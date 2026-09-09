from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger

class FirestoreService:
    """
    Cloud Firestore client scaffold for cloud deployment mode.
    Allows seamless transition from InMemory/Local storage to Google Cloud Firestore.
    """

    def __init__(self):
        self.project_id = settings.GOOGLE_CLOUD_PROJECT
        self.database = settings.FIRESTORE_DATABASE
        self.enabled = settings.ENABLE_FIRESTORE or settings.DATABASE_BACKEND.lower() == "firestore"
        self._db = None
        if self.enabled:
            logger.info(f"[FirestoreService] Initializing Firestore for project {self.project_id}")

    async def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        logger.debug(f"[FirestoreService] Scaffold get_document({collection}/{doc_id})")
        return None

    async def set_document(self, collection: str, doc_id: str, data: Dict[str, Any]) -> None:
        logger.debug(f"[FirestoreService] Scaffold set_document({collection}/{doc_id})")

    async def query_collection(self, collection: str, filters: List[tuple]) -> List[Dict[str, Any]]:
        logger.debug(f"[FirestoreService] Scaffold query_collection({collection})")
        return []

firestore_service = FirestoreService()
