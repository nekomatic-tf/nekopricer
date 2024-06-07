# Pricer Service

import logging
from src.database import ListingDBManager
from src.storage import MinIOEngine
from asyncio import run
from httpx import AsyncClient
from threading import Thread
from tf2_utils import PricesTF
from time import sleep
from src.server import socket_io

class Pricer():
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            mongo_uri: str,
            database_name: str,
            collection_name: str,
            storage_engine: MinIOEngine,
            items: dict,
    ):
        self.storage_engine = storage_engine
        self.items = items
        self.http_client = AsyncClient()
        self.database = ListingDBManager(mongo_uri, database_name, collection_name)
        self.prices_tf = PricesTF()
        self.pricelist_array = dict()
        self.key_price = dict()
        return
    
    def start(self):
        run(self._run())
    
    async def _run(self):
        keyprice_thread = Thread(target=self.get_keyprice)
        keyprice_thread.start()
        return

    async def price_items():
        return
    
    def get_keyprice(self): # Get and emit the key price every 5 minutes
        while True:
            try:
                self.prices_tf.request_access_token()
                key_price = self.prices_tf.get_price("5021;6")
                self.key_price = self.prices_tf.format_price(key_price)
                self.logger.info("Emitted new key price.")
            except Exception:
                self.logger.error("Failed to get key price from prices.tf!")
            sleep(300)