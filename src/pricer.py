# Pricer pricelist helper

import logging
from src.database import ListingDBManager
from asyncio import new_event_loop
from requests import post
from src.helpers import set_interval_and_wait
from src.pricelist import Pricelist

class Pricer:
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            config: dict,
            pricelist: Pricelist
    ):
        self.database = ListingDBManager(
            mongo_uri=config["mongo"]["uri"],
            database_name=config["mongo"]["db"],
            collection_name=config["mongo"]["collection"]
        )
        self.price_interval = config["intervals"]["price"]
        self.max_percentage_differences = config["maxPercentageDifferences"]
        self.excluded_steam_ids = config["excludedSteamIDs"]
        self.trusted_steam_ids = config["trustedSteamIDs"]
        self.excluded_listing_descriptions = config["excludedListingDescriptions"]
        self.blocked_attributes = config["blockedAttributes"]
        self.schema_server_url = config["pricesTf"]["schemaServer"]
        self.pricelist = pricelist
        self.event_loop = new_event_loop()
        # Get the pricelist and item list
        self.pricelist_array = dict()
        self.key_price = dict()
        set_interval_and_wait(self.price_items, self.price_interval)
        return

    def price_items(self):
        # Get all the SKUs
        total = 0
        remaining = 0
        custom = 0
        pricestf = 0
        failed = 0
        try:
            items = []
            for item in self.pricelist.item_list["items"]:
                items.append(item["name"])
            self.pricelist.get_external_pricelist()
            skus = post(f"{self.schema_server_url}/getSku/fromNameBulk", json=items)
            if not skus.status_code == 200:
                raise Exception("Issue converting names to SKUs.")
            if not type(skus.json()) == dict:
                raise Exception("Issue converting names to SKUs.")
            skus = skus.json()["skus"]
            total = len(skus)
            remaining = total
            skus = [{"sku": sku, "name": name} for sku, name in zip(skus, items)] # Produce a reasonable format iterate
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
                        price = self.pricelist.get_external_price(sku)
                        self.pricelist.update_price(price)
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
            self.pricelist.write_pricelist()
            self.pricelist.emit_prices()
            self.logger.info(f"\nDONE\nTotal:     {total}\nRemaining: {remaining}\nCustom:    {custom}\nPrices.TF: {pricestf}\nFailed:    {failed}")
            self.logger.info(f"Sleeping for {self.price_interval} seconds (If this is the interval loop).")
        except Exception as e:
            self.logger.error(e)