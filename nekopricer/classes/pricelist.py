from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from requests import get, post
from json import dumps, loads
from tf2_utils import PricesTF
from time import time, sleep
from threading import Thread
from urllib.parse import quote
from jsonschema import validate
from ..schemas.item_list import item_list_schema
from ..schemas.pricelist import pricelist_schema


class Pricelist:
    logger = getLogger("Pricelist")

    item_list: list = []
    external_pricelist: list = []
    pricelist: list = []
    old_pricelist: list = []
    key_price: dict = {}

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.prices_tf = PricesTF()

        self.fetch_external_pricelist_thread = Thread(target=self.fetch_external_pricelist_loop)
        self.refresh_key_price_thread = Thread(target=self.refresh_key_price_loop)

        self.fetch_external_pricelist_thread.daemon = True
        self.refresh_key_price_thread.daemon = True

    def start(self):
        self.read_item_list()
        self.read_pricelist()
        self.fetch_external_pricelist()
        self.refresh_key_price()
        self.freeze_pricelist()  # Keep a copy at startup
        self.fetch_external_pricelist_thread.start()
        self.refresh_key_price_thread.start()

    def read_item_list(self):
        try:
            if not self.pricer.minio.file_exists("item-list.json"):
                self.logger.debug("Attempting to new create item-list.json...")
                self.pricer.minio.write_file("item-list.json", dumps({"items": self.item_list}))
            item_list = loads(self.pricer.minio.read_file("item-list.json"))
            validate(item_list, item_list_schema)
            self.item_list = item_list["items"]
            self.logger.info("Read item list.")
        except Exception as e:
            self.logger.error(f"Failed to read item list: {e}")

    def write_item_list(self):
        try:
            validate({"items": self.item_list}, item_list_schema)
            self.pricer.minio.write_file("item-list.json", dumps({"items": self.item_list}))
            self.logger.info("Wrote item list.")
        except Exception as e:
            self.logger.error(f"Failed to write item list: {e}")

    def fetch_external_pricelist(self):
        try:
            response = get(f"{self.pricer.options.autobotTfUrl}/json/pricelist-array")
            if not response.status_code == 200:
                raise Exception(f"Recieved error code {response.status_code}.")
            if not len(response.json()["items"]) > 0:
                raise Exception("No items were found in the external pricelist.")
            self.logger.info("Fetched external pricelist.")
            self.external_pricelist = response.json()["items"]
            self.write_external_pricelist()
        except Exception as e:
            self.logger.error(f"An error occurred fetching the external pricelist array: {e}")
            self.read_external_pricelist()

    def write_external_pricelist(self):
        try:
            self.pricer.minio.write_file("external-pricelist.json", dumps({"items": self.external_pricelist}))
            self.logger.info("Saved external pricelist.")
        except Exception as e:
            self.logger.error(f"Failed to save external pricelist: {e}")

    def read_external_pricelist(self):
        try:
            if self.pricer.minio.file_exists("external-pricelist.json"):
                self.external_pricelist = loads(self.pricer.minio.read_file("external-pricelist.json"))["items"]
                self.logger.info("Read external pricelist.")
        except Exception as e:
            self.logger.error(f"Failed to read external pricelist: {e}")

    def get_external_price(self, item: dict) -> dict:
        try:
            if not item["sku"] == "5021;6":
                for external_price in self.external_pricelist:
                    if external_price["sku"] == item["sku"]:
                        self.logger.debug(f"Got external price for {item["name"]}/{item["sku"]} from the external pricelist.")
                        return external_price
            self.logger.debug(f"Falling back to prices.tf for {item["name"]}/{item["sku"]}.")
            self.prices_tf.request_access_token()
            prices_tf_price = self.prices_tf.get_price(item["sku"])
            currencies = self.prices_tf.format_price(prices_tf_price)
            self.logger.debug(f"Got external price for {item["name"]}/{item["sku"]} from prices.tf.")
            return {
                "name": item["name"],
                "sku": item["sku"],
                "source": "prices.tf",
                "time": int(time()),
                "buy": currencies["buy"],
                "sell": currencies["sell"],
            }
        except Exception as e:
            self.logger.error(f"Failed getting external price for {item["name"]}/{item["sku"]}: {e}")
            return None

    def refresh_key_price(self):
        if not self.pricer.options.jsonOptions["enforceKeyFallback"] and not self.key_price == {}:
            try:
                key_price = self.pricer.calculate_price({"name": "Mann Co. Supply Crate Key", "sku": "5021;6"})
                self.update_price(key_price)
                self.emit_price(key_price)
                self.key_price = key_price
                self.logger.info("Refreshed key price using custom logic.")
                return  # Completely exit the function
            except Exception as e:
                self.logger.error(f"Failed to refresh key price using custom logic: {e}")
        key_price = self.get_external_price({"name": "Mann Co. Supply Crate Key", "sku": "5021;6"})
        if key_price is None and self.key_price == {}:
            self.logger.error("Unrecoverable error detected.")
            raise Exception("Failed to retrieve key price for the first time.")
        if key_price is None:
            self.logger.error("Failed to refresh key price using fallback, key rate has NOT changed.")
        else:
            self.update_price(key_price)
            self.emit_price(key_price)
            self.key_price = key_price
            self.logger.info("Refreshed key price using fallback.")

    def read_pricelist(self):
        try:
            if not self.pricer.minio.file_exists("pricelist.json"):
                self.logger.debug("Attempting to create new pricelist.json...")
                self.pricer.minio.write_file("pricelist.json", dumps({"items": self.pricelist}))
            pricelist = loads(self.pricer.minio.read_file("pricelist.json"))
            validate(pricelist, pricelist_schema)
            self.pricelist = pricelist["items"]
            self.logger.info("Read pricelist.")
        except Exception as e:
            self.logger.error(f"Failed to read pricelist: {e}")

    def write_pricelist(self):
        try:
            validate({"items": self.pricelist}, pricelist_schema)
            self.pricer.minio.write_file("pricelist.json", dumps({"items": self.pricelist}))
            self.logger.info("Wrote pricelist.")
        except Exception as e:
            self.logger.error(f"Failed to write pricelist: {e}")

    def update_price(self, new_price: dict):
        for price in self.pricelist:
            if price["sku"] == new_price["sku"]:
                if price["buy"] == new_price["buy"] and price["sell"] == new_price["sell"]:
                    self.logger.info(f"Price for {price["name"]}/{price["sku"]} has not changed.")
                    break
                else:
                    price_index = self.pricelist.index(price)
                    self.pricelist[price_index] = new_price
                    self.write_pricelist()
                    self.logger.info(f"Updated price for {new_price["name"]}/{new_price["sku"]}.")
                    break
        else:
            self.pricelist.append(new_price)
            self.write_pricelist()
            self.logger.info(f"Added price for {new_price["name"]}/{new_price["sku"]}.")

    def get_price(self, item: dict) -> dict:
        for price in self.pricelist:
            if price["sku"] == item["sku"]:
                return price
        else:
            return None

    def update_pricelist(self, new_pricelist: list):
        self.old_pricelist = self.pricelist.copy()  # Take a snapshot of the old pricelist
        skipped = 0
        updated = 0
        for price in self.pricelist:
            for new_price in new_pricelist:
                if price["sku"] == new_price["sku"]:
                    if price["buy"] == new_price["buy"] and price["sell"] == new_price["sell"]:
                        self.logger.debug(f"Price for {price["name"]}/{price["sku"]} has not changed.")
                        skipped += 1
                        break
                    else:
                        self.logger.debug(f"Updating price for {price["name"]}/{price["sku"]}.")
                        price_index = self.pricelist.index(price)
                        self.pricelist[price_index] = new_price
                        updated += 1
                        break
            else:
                self.logger.debug(f"Adding new price for {price["name"]}/{price["sku"]}.")
                self.pricelist.append(price)
                updated += 1
        self.logger.info(f"Updated pricelist (Total: {skipped + updated}) (Skipped: {skipped}) (Updated: {updated})")

    def freeze_pricelist(self):
        self.old_pricelist = self.pricelist.copy()
        self.logger.debug("Freezed pricelist.")

    def add_item(self, name: str) -> bool:
        for item in self.item_list:
            if item["name"] == name:
                self.logger.warning(f"{name} is already in the item list.")
                return False
        else:
            self.item_list.append({"name": name})
            self.logger.info(f"Added {name} to the item list.")
            self.write_item_list()
            return True

    def get_item(self, name: str) -> dict:  # This will probably be useful in the future
        for item in self.item_list:
            if item["name"] == name:
                return item
        else:
            self.logger.error(f"Failed to find {name} in the item list.")
            return None

    def remove_item(self, name: str) -> bool:
        for item in self.item_list:
            if item["name"] == name:
                self.item_list.remove(item)
                self.logger.info(f"Removed {name} from the item list.")
                self.write_item_list()
                return True
        else:
            self.logger.error(f"Failed to find {name} in the item list.")
            return False

    def emit_price(self, item: dict):
        self.pricer.server.emit_to_clients("price", item)
        self.logger.info(f"Emitted price for {item["name"]}/{item["sku"]}.")

    def emit_prices(self):  # Only emits updated prices based on old_pricelist
        total = len(self.pricelist)
        skipped = 0
        emitted = 0
        for price in self.pricelist:
            for old_price in self.old_pricelist:
                if price["sku"] == old_price["sku"]:
                    if price["time"] == old_price["time"]:
                        self.logger.info(f"({emitted + skipped} / {total}) Price for {price["name"]}/{price["sku"]} has not changed.")
                        skipped += 1
                        break  # Skip
                    else:
                        self.pricer.server.emit_to_clients("price", price)
                        self.logger.info(f"({emitted + skipped} / {total}) Emitted price for {price["name"]}/{price["sku"]}.")
                        emitted += 1
                        sleep(0.3)
                        break  # Update
            else:
                self.pricer.server.emit_to_clients("price", price)
                self.logger.info(f"({emitted + skipped} / {total}) Emitted price for {price["name"]}/{price["sku"]}.")
                emitted += 1
                sleep(0.3)
        self.logger.info(f"Emitted new prices (Total: {total}) (Skipped: {skipped}) (Emitted: {emitted})")

    def emit_all_prices(self):
        total = len(self.pricelist)
        emitted = 0
        for price in self.pricelist:
            self.pricer.server.emit_to_clients("price", price)
            self.logger.info(f"Emitted price for {price["name"]}/{price["sku"]}.")
            emitted += 1
            sleep(0.3)
        self.logger.info(f"Emitted all prices (Total: {total}) (Emitted: {emitted})")

    # Loops
    def fetch_external_pricelist_loop(self):
        delay = self.pricer.options.jsonOptions["intervals"]["pricelist"]
        self.logger.debug(f"Fetching external pricelist again in {delay} seconds.")
        sleep(delay)
        self.fetch_external_pricelist()
        self.fetch_external_pricelist_loop()

    def refresh_key_price_loop(self):
        delay = self.pricer.options.jsonOptions["intervals"]["key"]
        self.logger.debug(f"Refreshing key price again in {delay} seconds.")
        sleep(delay)
        self.refresh_key_price()
        self.refresh_key_price_loop()

    # Helpers
    def to_sku(self, name: str) -> str:
        try:
            response = get(f"{self.pricer.options.autobotTfSchemaUrl}/getSku/fromName/{quote(name)}")
            if not response.status_code == 200:
                raise Exception(f"Response returned status code {response.status_code}.")
            if type(response.json()) is not dict:
                raise Exception(f"Response is not of type {dict}.")
            return response.json()["sku"]
        except Exception as e:
            self.logger.error(f"Failed to convert {name} to SKU: {e}")
            return None

    def to_name(self, sku: str) -> str:
        try:
            response = get(
                url=f"{self.pricer.options.autobotTfSchemaUrl}/getName/fromSku/{quote(sku)}",
                params={"proper": "true"},
            )
            if not response.status_code == 200:
                raise Exception(f"Response returned status code {response.status_code}.")
            if type(response.json()) is not dict:
                raise Exception(f"Response is not of type {dict}.")
            return response.json()["name"]
        except Exception as e:
            self.logger.error(f"Failed to convert SKU {sku} to name: {e}")
            return None

    def to_sku_bulk(self, names: list[str]) -> list[str]:
        try:
            response = post(
                url=f"{self.pricer.options.autobotTfSchemaUrl}/getSku/fromNameBulk",
                json=names,
            )
            if not response.status_code == 200:
                raise Exception(f"Response returned status code {response.status_code}.")
            if type(response.json()) is not dict:
                raise Exception(f"Response is not of type {dict}.")
            return response.json()["skus"]
        except Exception as e:
            self.logger.error(f"Failed to convert names into SKUS: {e}")
            return None

    def to_name_bulk(self, skus: list[str]) -> list[str]:
        try:
            response = post(
                url=f"{self.pricer.options.autobotTfSchemaUrl}/getName/fromSkuBulk",
                json=skus,
                params={"proper": "true"},
            )
            if not response.status_code == 200:
                raise Exception(f"Response returned status code {response.status_code}.")
            if type(response.json()) is not dict:
                raise Exception(f"Response is not of type {dict}.")
            return response.json()["names"]
        except Exception as e:
            self.logger.error(f"Failed to convert SKUS into names: {e}")
            return None

    # Return high level statistics of the pricelist manager
    def get_statistics(self) -> dict:
        statistics = {
            "custom": sum(1 for item in self.pricelist if item["source"] == "nekopricer"),
            "fallback": sum(1 for item in self.pricelist if not item["source"] == "nekopricer"),
            "total": len(self.pricelist),
            "updated": 0,
            "skipped": 0,
            "key_rate": {
                "buy": self.key_price["buy"]["metal"],
                "sell": self.key_price["sell"]["metal"],
                "source": self.key_price["source"],
            },
        }
        for price in self.pricelist:
            for old_price in self.old_pricelist:
                if price["sku"] == old_price["sku"]:
                    if price["time"] == old_price["time"]:
                        statistics["skipped"] += 1
                        break
                    else:
                        statistics["updated"] += 1
                        break
            else:
                statistics["updated"] += 1
        return statistics
