# Pricer pricelist helper

import logging
from src.database import ListingDBManager
from src.storage import MinIOEngine
from asyncio import new_event_loop
import requests
from src.helpers import set_interval, compare_prices, set_interval_and_wait
from tf2_utils import PricesTF
from time import time
from minio import S3Error
from json import loads, dumps
from flask_socketio import SocketIO
from time import sleep
from threading import Thread

class Pricer:
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            mongo_uri: str,
            database_name: str,
            collection_name: str,
            storage_engine: MinIOEngine,
            schema_server_url: str,
            socket_io: SocketIO,
            pricing_interval: float,
            max_percentage_differences: dict,
            excluded_steam_ids: list,
            trusted_steam_ids: list,
            excluded_listing_descriptions: list,
            blocked_attributes: dict
    ):    
        self.database = ListingDBManager(mongo_uri, database_name, collection_name)
        self.event_loop = new_event_loop()
        self.storage_engine = storage_engine
        self.schema_server_url = schema_server_url
        self.socket_io = socket_io
        self.pricing_interval = pricing_interval
        self.max_percentage_differences = max_percentage_differences
        self.excluded_steam_ids = excluded_steam_ids
        self.trusted_steam_ids = trusted_steam_ids
        self.excluded_listing_descriptions = excluded_listing_descriptions
        self.blocked_attributes = blocked_attributes
        # Get the pricelist and item list
        self.pricelist_array = dict()
        self.key_price = dict()
        self.items = dict()
        self.pricelist = dict()
        self.pricestf = PricesTF()
        # Get our data before full initialization
        self.read_items()
        self.write_items() # For good measure
        self.read_pricelist()
        self.write_pricelist() # For good measure
        self.update_pricelist_array()
        self.update_key_price()
        set_interval(self.update_pricelist_array, 300) # 5 Minutes
        set_interval(self.update_key_price, 300) # 5 Minutes
        Thread(target=self.price_items).start() # Price items ONE time during startup
        set_interval_and_wait(self.price_items, pricing_interval)
        return
    
    # Tasks
    def update_key_price(self):
        try:
            self.logger.debug("Refreshing key price...")
            price = self.get_external_price("5021;6")
            if price == None:
                raise Exception("Failed to get the key price.")
            self.key_price = price
            self.update_pricelist(price)
            self.socket_io.emit("price", price)
            self.logger.info("Refreshed key price.")
        except Exception as e:
            self.logger.error(e)
    
    def update_pricelist_array(self):
        try:
            self.logger.debug("Refreshing external pricelist...")
            response = requests.get("https://autobot.tf/json/pricelist-array")
            if not response.status_code == 200:
                raise Exception("Failed to fetch external pricelist.")
            if not len(response.json()["items"]) > 0:
                raise Exception("No items were found in the external pricelist.")
            self.pricelist_array = response.json()["items"]
            self.logger.info("Refreshed pricelist array.")
        except Exception as e:
            self.logger.error("Failed to update the pricelist array.")
            self.logger.error(e)

    def price_items(self):
        # Get all the SKUs
        total = 0
        remaining = 0
        custom = 0
        pricestf = 0
        failed = 0
        try:
            self.update_pricelist_array() # Update before pricing
            skus = requests.post(f"{self.schema_server_url}/getSku/fromNameBulk", json=self.items["items"])
            if not skus.status_code == 200:
                raise Exception("Issue converting names to SKUs.")
            if not type(skus.json()) == dict:
                raise Exception("Issue converting names to SKUs.")
            skus = skus.json()["skus"]
            total = len(skus)
            remaining = total
            skus = [{"sku": sku, "name": name} for sku, name in zip(skus, self.items["items"])] # Produce a reasonable format iterate
            for sku in skus:
                try:
                    #listings = self.event_loop.run_until_complete(self.database.get_listings(sku["name"]))
                    if sku["sku"] == "5021;6":     
                        remaining -= 1
                        pricestf += 1
                        continue # We don't price the key
                    raise Exception("Cannot price yet.")
                    custom += 1
                    self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using pricer.")
                except Exception as e:
                    self.logger.error(f"Failed to price item {sku["name"]}/{sku["sku"]} using pricer.")
                    self.logger.error(e)
                    try:
                        price = self.get_external_price(sku["sku"])
                        self.update_pricelist(price)
                        remaining -= 1
                        pricestf += 1
                        self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using fallback.")
                    except Exception as e:
                        self.logger.error(f"Failed to price {sku["name"]}/{sku["sku"]} using fallback.")
                        self.logger.error(e)
                        print("!! THIS IS VERY BAD CHECK CODE !!")
                        failed += 1
                        remaining -= 1
                self.logger.info(f"\nTotal:     {total}\nRemaining: {remaining}\nCustom:    {custom}\nPrices.TF: {pricestf}\nFailed:    {failed}")
            self.write_pricelist()
            prices = self.pricelist["items"]
            total = len(prices)
            remaining = 0
            for price in prices:
                self.socket_io.emit("price", price)
                remaining = remaining + 1
                self.logger.info(f"({remaining} out of {total}) Emitted price for {price["name"]}/{price["sku"]}")
                sleep(0.3)
            self.logger.info(f"\nDONE\nTotal:     {total}\nRemaining: {remaining}\nCustom:    {custom}\nPrices.TF: {pricestf}\nFailed:    {failed}")
            self.logger.info(f"Sleeping for {self.pricing_interval} seconds (If this is the interval loop).")
        except Exception as e:
            self.logger.error(e)

    # Functions
    def get_external_price(self, sku: str) -> dict:
        try:
            self.logger.debug(f"Getting external price for {sku}")
            for item in self.pricelist_array:
                if sku == "5021;6": # Nope, get fallback'd
                    self.logger.debug("Forcing Mann Co. Supply Crate Key (5021;6) to use prices.tf API.")
                    break
                if sku == item["sku"]:
                    return item
            # Occurs if the item price isn't found in the external array
            if not sku == "5021;6": # It is not an error if its a key
                self.logger.warn(f"Failed to find price for {sku}, using prices.tf.")
            self.pricestf.request_access_token()
            item = self.pricestf.get_price(sku)
            name = requests.get(f"{self.schema_server_url}/getName/fromSku/{sku}")
            if not name.status_code == 200:
                raise Exception(f"Failed to get name for {sku}")
            name = name.json()["name"]
            price = self.pricestf.format_price(item)
            return {
                "name": name,
                "sku": sku,
                "source": "bptf",
                "time": int(time()),
                "buy": price["buy"],
                "sell": price["sell"]
            }
        except Exception as e:
            self.logger.error(f"Failed getting external price for {sku}")
            self.logger.error(e)
    
    # Helper methods
    def update_pricelist(self, item: dict):
        try:
            items = self.pricelist["items"] # Low level coding activities
            # Unused code, if the array is blank something went seriously fucking wrong anyways
            '''if not type(items) == list:
                items = []'''
            existing_index = next((index for index, pricelist_item in enumerate(items) if pricelist_item['sku'] == item['sku']), -1)
            if not existing_index == -1:
                pl_item = items[existing_index]
                if item["buy"] and item["sell"] and pl_item["buy"] and pl_item["sell"]:
                    # Update prices
                    items[existing_index] = item
                    self.logger.debug(f"Updated price for {item["name"]}/{item["sku"]}")
                elif item["buy"] and item["sell"] and (not pl_item["buy"] or not pl_item["sell"]):
                    # We have a buy and sell price, but the pricelist item doesn't.
                    items[existing_index] = item
                    self.logger.debug(f"Updated price for {item["name"]}/{item["sku"]}")
                else:
                    # Data is missing, don't update.
                    self.logger.debug(f"Skipping price update for {item["name"]}/{item["sku"]} (No data).")
                    return
            else:
                # If the item doesn't exist, add it to the end of the array
                items.append(item)
                self.pricelist["items"] = items
                self.write_pricelist()
        except Exception as e:
            self.logger.error(f"Failed updating price for {item["name"]}/{item["sku"]}")
            self.logger.error(e)
    
    def read_items(self):
        try:
            self.logger.debug("Reading items...")
            items = self.storage_engine.read_file("item_list.json")
            if type(items) == S3Error:
                self.logger.debug("Creating items...")
                self.storage_engine.write_file("item_list.json", "{\"items\":[]}")
                items = self.storage_engine.read_file("item_list.json")
            self.logger.info("Read items.")
            self.items = loads(items)
        except Exception as e:
            self.logger.error("Failed reading items.")
            self.logger.error(e)
    
    def write_items(self):
        try:
            self.logger.debug("Writing items...")
            self.storage_engine.write_file("item_list.json", dumps(self.items))
            self.logger.info("Wrote items.")
        except Exception as e:
            self.logger.error("Failed writing items.")
            self.logger.error(e)
    
    def read_pricelist(self):
        try:
            self.logger.debug("Reading pricelist...")
            pricelist = self.storage_engine.read_file("pricelist.json")
            if type(pricelist) == S3Error:
                self.logger.debug("Creating pricelist...")
                self.storage_engine.write_file("pricelist.json", "{\"items\":[]}")
                pricelist = self.storage_engine.read_file("pricelist.json")
            self.pricelist = loads(pricelist)
            self.logger.info("Read pricelist.")
        except Exception as e:
            self.logger.error("Failed reading pricelist.")
            self.logger.error(e)
    
    def write_pricelist(self):
        try:
            self.logger.debug("Writing pricelist...")
            self.storage_engine.write_file("pricelist.json", dumps(self.pricelist))
            self.logger.info("Wrote pricelist.")
        except Exception as e:
            self.logger.error("Failed writing pricelist.")
            self.logger.error(e)