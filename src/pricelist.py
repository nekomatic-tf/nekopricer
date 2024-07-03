# Pricelist Handler (Required by Pricer())

import logging
from src.storage import S3Engine
from json import loads, dumps
from requests import get, post
from src.helpers import set_interval
from tf2_utils import PricesTF
from time import time
from flask_socketio import SocketIO
from time import sleep
from urllib.parse import quote

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
        self.schema_server_url = config["pricesTf"]["schemaServer"]
        self.socket_io = socket_io
        self.read_item_list()
        self.write_item_list()
        self.get_external_pricelist()
        self.get_key_price()
        # self.read_pricelist()
        self.write_pricelist()
        set_interval(self.get_external_pricelist, config["intervals"]["pricelist"])
        if config["enforceKeyFallback"] == True: # Key is priced by external API
            self.logger.info("Key will be priced using the external pricelist.")
            set_interval(self.get_key_price, config["intervals"]["key"])
        set_interval(self.write_pricelist, config["intervals"]["pricelist"]) # Hardly needed since its erased at startup, but could change in the future, so we keep it
        return
    
    def add_item(self, name: str):
        for item in self.item_list["items"]:
            if item["name"] == name:
                self.logger.debug(f"{item["name"]} is already in item_list.")
                return
        self.item_list["items"].append({"name":name})
        self.logger.info(f"Added {name} to the item list.")
        self.write_item_list()
        return
    def remove_item(self, name: str):
        for item in self.item_list["items"]:
            if item["name"] == name:
                self.item_list["items"].remove(item)
                self.logger.info(f"Removed {item["name"]} from the item list.")
                self.write_item_list()
                return
        self.logger.debug(f"{name} not found in item_list.")
        return
    def get_price(self, sku: str):
        for item in self.pricelist["items"]:
            if item["sku"] == sku:
                return item
        return None
    def update_price(self, item: dict):
        for p_item in self.pricelist["items"]:
            if item["name"] == p_item["name"] or item["sku"] == p_item["sku"]:
                self.pricelist["items"].remove(p_item)
                break
        self.pricelist["items"].append(item)
        self.logger.info(f"Updated pricelist with new price for {item["name"]}/{item["sku"]}.")
        return
    def emit_price(self, item: dict):
        self.socket_io.emit("price", item)
        self.logger.info(f"Emitted price for {item["name"]}/{item["sku"]}.")
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
            self.logger.info(f"({done} out of {total}) Emitted price for {item["name"]}/{item["sku"]}.")
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
        try:
            self.key_price = self.get_external_price({
                "sku": "5021;6",
                "name": "Mann Co. Supply Crate Key"
            })
            self.update_price(self.key_price)
            self.emit_price(self.key_price)
            self.logger.info("Refreshed price for Mann Co. Supply Crate Key/5021;6.")
        except Exception as e:
            self.logger.error(f"Failed refreshing price for Mann Co. Supply Crate Key/5021;6: {e}")
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
    # SKU Conversion Kit Premium Edition
    def to_sku(self, name: str):
        sku = get(
            url=f"{self.schema_server_url}/getSku/fromName/{quote(name)}"
        )
        if not sku.status_code == 200:
            raise Exception("Issue converting name to SKU.")
        if not type(sku.json()) == dict:
            raise Exception("Issue converting name to SKU.")
        return sku.json()["sku"]
    def to_name(self, sku: str):
        name = get(
            url=f"{self.schema_server_url}/getName/fromSku/{quote(sku)}",
            params={"proper": "true"}
        )
        if not name.status_code == 200:
            raise Exception("Issue converting SKU to name.")
        if not type(name.json()) == dict:
            raise Exception("Issue converting SKU to name.")
        return name.json()["name"]
    def to_sku_bulk(self, names: list):
        skus = post(
            url=f"{self.schema_server_url}/getSku/fromNameBulk",
            json=names
        )
        if not skus.status_code == 200:
            raise Exception("Issue converting names to SKUs.")
        if not type(skus.json()) == dict:
            raise Exception("Issue converting names to SKUs.")
        return skus.json()["skus"]
    def to_name_bulk(self, skus: list):
        names = post(
            url=f"{self.schema_server_url}/getName/fromSkuBulk",
            json=skus,
            params={"proper": "true"}
        )
        if not names.status_code == 200:
            raise Exception("Issue converting SKUs into names.")
        if not type(names.json()) == dict:
            raise Exception("Issue converting SKUs into names.")
        return names.json()["names"]