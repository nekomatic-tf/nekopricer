# Pricer pricelist helper

import logging
from src.database import ListingDBManager
from src.storage import MinIOEngine
from asyncio import new_event_loop
import requests
from src.helpers import set_interval

class Pricelist:
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            mongo_uri: str,
            database_name: str,
            collection_name: str,
            storage_engine: MinIOEngine,
            schema_server_url: str
    ):
        self.database = ListingDBManager(mongo_uri, database_name, collection_name)
        self.event_loop = new_event_loop()
        self.storage_engine = storage_engine
        self.schema_server_url: schema_server_url
        # Get the pricelist and item list
        self.pricelist_array = dict()
        self.update_pricelist_array()
        set_interval(self.update_pricelist_array, 5) # 5 Minutes
        return
    
    # Tasks
    def update_key_price(self):
        print("test")
        return
    
    def update_pricelist_array(self):
        try:
            self.logger.debug("Getting external pricelist...")
            response = requests.get("https://autobot.tf/json/pricelist-array")
            if not response.status_code == 200:
                raise Exception("Failed to fetch external pricelist.")
            if not len(response.json()["items"]) > 0:
                raise Exception("No items were found in the external pricelist.")
            self.pricelist_array = response.json()["items"]
            self.logger.info("Refreshed pricelist array.")
        except Exception as e:
            self.logger.error(e)
    
    # Functions
    def get_external_price(self, sku):
        return
    
    def update_pricelist(self):
        return
    
    def read_items(self):
        return
    
    def write_items(self):
        return
    
    def read_pricelist(self):
        return
    
    def write_pricelist(self):
        return