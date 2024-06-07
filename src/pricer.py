# Pricer Service

import logging
from src.database import ListingDBManager
from src.storage import MinIOEngine
from asyncio import run
from httpx import AsyncClient
from threading import Thread
from tf2_utils import PricesTF
from time import sleep, time
from src.server import socket_io
from minio import S3Error
from json import loads

class Pricer():
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            mongo_uri: str,
            database_name: str,
            collection_name: str,
            storage_engine: MinIOEngine,
            items: dict,
            schema_server_url: str
    ):
        self.storage_engine = storage_engine
        self.items = items
        self.schema_server_url = schema_server_url
        self.http_client = AsyncClient()
        self.database = ListingDBManager(mongo_uri, database_name, collection_name)
        self.prices_tf = PricesTF()
        self.pricelist_array = dict()
        self.key_price = dict()
        return
    
    def start(self):
        run(self._run())
    
    async def _run(self):
        await self.price_items()
        return

    async def price_items(self):
        array = await self.get_pricelist_array()
        if not type(array) == list:
            raise Exception("Failed to get external pricelist array.")
        self.pricelist_array = array
        price = await self.get_external_price("5021;6")
        if not type(price) == dict:
            raise Exception("Failed to get key price.")
        self.key_price = price
        socket_io.emit("price", price)
        self.logger.info("Emitted new key price.")
        for item in self.items:
            
            return
        sleep(300) # Every 5 minutes, just temporary

        await self.price_items()
        return
    
    async def get_external_price(self, sku: str) -> dict: # Properly formats a prices.tf price.
        try:
            for item in self.pricelist_array:
                if sku == "5021;6": # Nope, get fallback'd
                    break
                if sku == item["sku"]:
                    return item
            # Occurs if the item price isn't found in the external array or the SKU is a that of a key
            self.logger.debug("Failed to find item in pricelist array, calling prices.tf")
            self.prices_tf.request_access_token()
            item = self.prices_tf.get_price(sku)
            item_name = await self.http_client.get(f"{self.schema_server_url}/getName/fromSku/{sku}")
            if not item_name.status_code == 200:
                raise Exception(f"Failed to fetch get name for {sku}")
            item_name = item_name.json()["name"]
            price = self.prices_tf.format_price(item)
            return {
                "name": item_name,
                "sku": sku,
                "source": "bptf",
                "time": int(time()),
                "buy": price["buy"],
                "sell": price["sell"]
            }
        except Exception as e:
            return e
    
    async def get_pricelist_array(self):
        try:
            response = await self.http_client.get("https://autobot.tf/json/pricelist-array")
            if not response.status_code == 200:
                raise Exception("Failed to fetch external pricelist.")
            if not len(response.json()["items"]) > 0:
                raise Exception("No items were found in the external pricelist.")
            return response.json()["items"]
        except Exception as e:
            return e
    
    def update_pricelist_file(self): # Updates the custom pricelist (Kinda important for the API to work)
        pricelist = self.storage_engine.read_file("pricelist.json")
        if (type(pricelist) == S3Error):
            self.logger.debug("Creating pricelist.json")
            self.storage_engine.write_file("pricelist.json", "{\"items\": []}")
            pricelist = self.storage_engine.read_file("pricelist.json")
        pricelist = loads(pricelist)
        return