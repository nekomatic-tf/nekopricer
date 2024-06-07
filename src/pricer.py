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
from json import loads, dumps

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
        await self._refresh_key_price() # Refresh before doing literally anything
        key_thread = Thread(target=self.refresh_key_price)
        key_thread.start()
        await self.price_items()
        return
    
    def refresh_key_price(self):
        run(self._refresh_key_price())
        sleep(300) # 5 minutes of eepy
        self.refresh_key_price()
    
    async def _refresh_key_price(self):
        try:
            pricelist_array = await self.get_pricelist_array()
            print(pricelist_array)
            if not type(pricelist_array) == list:
                raise Exception("Failed to get external pricelist array.")
            self.pricelist_array = pricelist_array
            key_price = await self.get_external_price("5021;6")
            if not type(key_price) == dict:
                raise Exception("Failed to get key price.")
            self.key_price = key_price
            socket_io.emit("price", key_price)
            self.update_pricelist_file(self.key_price)
            self.logger.info("Emitted new key price.")
        except Exception as e:
            self.logger.error(str(e))


    async def price_items(self):
        # Get all the SKUs
        try:
            skus = await self.http_client.post(f"{self.schema_server_url}/getSku/fromNameBulk", json=self.items)
            if not skus.status_code == 200:
                raise Exception("Issue converting names to SKUs.")
            if not type(skus.json()) == dict:
                raise Exception("Issue converting names to SKUs.")
            for sku in skus.json()["skus"]:
                if sku == "5021;6":
                    return # Skip the key
                price = await self.get_external_price(sku)
                self.update_pricelist_file(price)
                #socket_io.emit("price", price)
            print("snoozing")
            sleep(5) # Every 5 minutes, just temporary
            print("snoozed")
            await self.price_items()
            return
        except Exception as e:
            self.logger.error(e)

    
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
    
    def update_pricelist_file(self, item: dict): # Updates the custom pricelist (Kinda important for the API to work)
        try:
            pricelist = self.storage_engine.read_file("pricelist.json")
            if (type(pricelist) == S3Error):
                self.logger.debug("Creating pricelist.json")
                self.storage_engine.write_file("pricelist.json", "{\"items\": []}")
                pricelist = self.storage_engine.read_file("pricelist.json")
            pricelist = loads(pricelist)
            items = pricelist["items"]
            if not type(items) == list:
                items = []
            existing_index = next((index for index, pricelist_item in enumerate(items) if pricelist_item['sku'] == item['sku']), -1)

            if not existing_index == -1:
                pl_item = items[existing_index]
                if item["buy"] and item["sell"] and pl_item["buy"] and pl_item["sell"]:
                    if compare_prices(pl_item["buy"], item["buy"]) and compare_prices(pl_item["sell"], item["sell"]):
                        # Prices are the same, no need to update
                        return
                    else:
                        # Prices are different, update.
                        items[existing_index] = item
                elif item["buy"] and item["sell"] and (not pl_item["buy"] or not pl_item["sell"]):
                    # We have a buy and sell price, but the pricelist item doesn't.
                    items[existing_index] = item
                else:
                    # Data is missing, don't update.
                    return
            else:
                # If the item doesn't exist, add it to the end of the array
                items.append(item)
                pricelist["items"] = items
                self.storage_engine.write_file("pricelist.json", dumps(pricelist))
        except Exception as e:
            self.logger.error(e)

    
# Helpers
def compare_prices(item_1, item_2):
    return item_1["keys"] == item_2["keys"] and item_1["metal"] == item_2["metal"]