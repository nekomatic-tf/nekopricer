# Pricelist Handler (Required by Pricer())

import logging
from src.storage import S3Engine
from json import loads, dumps
from requests import get
from src.helpers import set_interval
from tf2_utils import PricesTF
from time import time
from flask_socketio import SocketIO
from time import sleep

class Pricelist:
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            config: dict,
            socket_io: SocketIO
    ):
        self.logger.info("Initializing S3...")
        self.storage_engine = S3Engine(config["minio"])
        self.item_list = {"items": []}
        self.pricelist = {"items": []}
        self.external_pricelist = dict()
        self.key_price = dict()
        self.logger.info("Initializing pricelist...")
        self.pricestf = PricesTF()
        self.autobot_server_url = config["pricesTf"]["autobotServer"]
        self.socket_io = socket_io
        self.read_item_list()
        self.write_item_list()
        self.get_external_pricelist()
        self.get_key_price()
        self.write_pricelist()
        set_interval(self.get_external_pricelist, config["intervals"]["pricelist"])
        if config["enforceKeyFallback"] == True: # Key is priced by external API
            self.logger.info("Key will be priced using the external pricelist.")
            set_interval(self.get_key_price, config["intervals"]["pricelist"])
        set_interval(self.write_pricelist, 300) # 5 Minutes, just to make sure it stays in sync
        return
    
    def add_item(self):
        return
    def remove_item(self):
        return
    def get_price(self):
        return
    def update_price(self, item: dict):
        for p_item in self.pricelist["items"]:
            if item["name"] == p_item["name"] or item["sku"] == p_item["sku"]:
                self.pricelist["items"].remove(p_item)
                break
        self.pricelist["items"].append(item)
        self.logger.info(f"Updated pricelist with new price for {item["name"]}/{item["sku"]}")
        return
    def emit_price(self, item: dict):
        self.socket_io.emit("price", item)
        self.logger.info(f"Emitted price for {item["name"]}/{item["sku"]}")
        return
    def emit_prices(self):
        total = len(self.pricelist["items"])
        done = 0
        for item in self.pricelist["items"]:
            if item["sku"] == "5021;6" or item["name"] == "Mann Co. Supply Crate Key": # Key price is emitted at a fixed interval
                done += 1
                continue
            self.socket_io.emit("price", item)
            done += 1
            self.logger.info(f"({done} out of {total}) Emitted price for {item["name"]}/{item["sku"]}")
            sleep(0.3)
        self.logger.info(f"Emitted prices for all {total} items.")
        return
    def read_item_list(self):
        try:
            self.item_list = loads(self.storage_engine.read_file("item_list.json"))
            self.logger.info("Read item_list.")
        except Exception as e:
            self.logger.warn("item_list not found, creating...")
            self.storage_engine.write_file("item_list.json", dumps(self.item_list))
            self.item_list = loads(self.storage_engine.read_file("item_list.json"))
            self.logger.info("Read item_list.")
    def write_item_list(self):
        self.storage_engine.write_file("item_list.json", dumps(self.item_list))
        self.logger.info("Wrote item_list.")
        return
    def read_pricelist(self):
        try:
            self.pricelist = loads(self.storage_engine.read_file("pricelist.json"))
            self.logger.info("Read pricelist.")
        except Exception as e:
            self.logger.warn("pricelist not found, creating...")
            self.storage_engine.write_file("pricelist.json", dumps(self.pricelist))
            self.pricelist = loads(self.storage_engine.read_file("pricelist.json"))
            self.logger.info("Read pricelist.")
    def write_pricelist(self):
        self.storage_engine.write_file("pricelist.json", dumps(self.pricelist))
        self.logger.info("Wrote pricelist.")
        return
    # Remove items that aren't in the item_list
    '''
    def clean_pricelist(self):
        p_items = []
        for item in self.item_list["items"]:
            for p_item in self.pricelist["items"]:
                if item["name"] == p_item["name"]:
                    p_items.append(p_item)
                    break
        self.logger.info(f"Cleaned {len(self.pricelist["items"]) - len(p_items)} item(s) off of the pricelist.")
        self.pricelist["items"] = p_items
        return
    '''
    def get_key_price(self):
        self.key_price = self.get_external_price({
            "sku": "5021;6",
            "name": "Mann Co. Supply Crate Key"
        })
        self.update_price(self.key_price)
        self.emit_price(self.key_price)
        return
    def get_external_pricelist(self):
        try:
            response = get(f"{self.autobot_server_url}/json/pricelist-array")
            if not response.status_code == 200:
                raise Exception(f"Error code {response.status_code}")
            if not len(response.json()["items"]) > 0:
                raise Exception("No items were found in the array.")
            self.external_pricelist = response.json()
            self.logger.info("Fetched external pricelist.")
            self.storage_engine.write_file("array.json", dumps(response.json()))
        except Exception as e:
            self.logger.error(f"Failed to fetch external pricelist: {e}")
    def get_external_price(self, item: dict):
        try:
            for e_item in self.external_pricelist["items"]:
                if e_item["sku"] == item["sku"] and not item["sku"] == "5021;6":
                    return e_item # We found the item, exit
            if not item["sku"] == "5021;6" or not item["name"] == "Mann Co. Supply Crate Key":
                self.logger.warning(f"Failed to find a price for {item["name"]}/{item["sku"]} in the pricelist array.")
            self.logger.info(f"Falling back to prices.tf for {item["name"]}/{item["sku"]}.")
            self.pricestf.request_access_token()
            ptf_item = self.pricestf.get_price(item["sku"])
            price = self.pricestf.format_price(ptf_item)
            return {
                "name": item["name"],
                "sku": item["sku"],
                "source": "bptf",
                "time": int(time()),
                "buy": price["buy"],
                "sell": price["sell"]
            }
        except Exception as e:
            self.logger.error(f"Failed getting price for {item["name"]}/{item["sku"]}: {e}")    