# Pricer Service

import logging
from src.database import ListingDBManager
from src.storage import MinIOEngine
from asyncio import run
from httpx import AsyncClient
from threading import Event

class Pricer():
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            mongo_uri: str,
            database_name: str,
            collection_name: str,
            storage_engine: MinIOEngine,
            items: dict
    ):
        self.storage_engine = storage_engine
        self.http_client = AsyncClient()
        self.items = items
        self.database = ListingDBManager(mongo_uri, database_name, collection_name)
        return
    
    def start(self, event: Event):
        run(self._run(event))
    
    async def _run(self, event: Event):
        return