# Pricer pricelist helper

import logging
from src.database import ListingDBManager
from asyncio import new_event_loop
from requests import post
from src.helpers import set_interval_and_wait
from src.pricelist import Pricelist
from threading import Thread
from math import floor
from time import time

class Pricer:
    logger = logging.getLogger(__name__)
    def __init__(
            self,
            config: dict,
            pricelist: Pricelist
    ):
        self.logger.info("Initializing pricer...")
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
        self.only_use_bots = config["onlyBots"]
        self.buy_listing_amount = config["buyListingAmount"]
        self.sell_listing_amount = config["sellListingAmount"]
        self.undercut = config["undercut"]
        self.overcut = config["overcut"]
        self.pricelist = pricelist
        self.event_loop = new_event_loop()
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
                    if sku["sku"] == "5021;6" or sku["name"] == "Mann Co. Supply Crate Key":     
                        remaining -= 1
                        pricestf += 1
                        continue # We don't price the key
                    price = self.calculate_price(sku) # Attempt to price this specific item (will throw an exception if it fails)
                    self.pricelist.update_price(price)
                    remaining -= 1
                    custom += 1
                    self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using pricer.")
                except Exception as e:
                    self.logger.error(f"Failed to price item {sku["name"]}/{sku["sku"]} using pricer: {e}")
                    try:
                        price = self.pricelist.get_external_price(sku)
                        self.pricelist.update_price(price)
                        remaining -= 1
                        pricestf += 1
                        self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using fallback.")
                    except Exception as e:
                        self.logger.error(f"Failed to price {sku["name"]}/{sku["sku"]} using fallback: {e}")
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
    
    def price_item(self, sku: dict): # Simply runs the protocol to price a specific item (useful for pricecheck?)
        return
    
    def calculate_price(self, sku: dict):
        buy_listings = self.event_loop.run_until_complete(self.database.get_listings_by_intent(sku["name"], "buy"))
        sell_listings = self.event_loop.run_until_complete(self.database.get_listings_by_intent(sku["name"], "sell"))
        # Perform a series of filtering before making sure we have enough listings
        # Filter out excluded steam ids
        buy_listings = [listing for listing in buy_listings if listing["steamid"] not in self.excluded_steam_ids]
        sell_listings = [listing for listing in sell_listings if listing["steamid"] not in self.excluded_steam_ids]
        if self.only_use_bots == True: # Filter out listings without a user agent
            buy_listings = [listing for listing in buy_listings if listing["user_agent"] is not None]
            sell_listings = [listing for listing in sell_listings if listing["user_agent"] is not None]
        # Filter out excluded listing descriptions
        buy_listings = [listing for listing in buy_listings if all(excluded not in listing["details"] for excluded in self.excluded_listing_descriptions)]
        sell_listings = [listing for listing in sell_listings if all(excluded not in listing["details"] for excluded in self.excluded_listing_descriptions)]
        # Filter out marketplace.tf listings
        buy_listings = [listing for listing in buy_listings if "usd" not in listing["currencies"]]
        sell_listings = [listing for listing in sell_listings if "usd" not in listing["currencies"]]
        # Filter out blocked attributes (ILL DO THIS LATER)
        # Make sure we have enough listings to do some math
        if len(buy_listings) == 0:
            raise Exception("No buy listings were found.")
        # Sort from lowest to high and highest to low
        buy_listings = sorted(buy_listings, key=lambda x: self.to_metal(x["currencies"], self.pricelist.key_price["buy"]), reverse=True)
        sell_listings = sorted(sell_listings, key=lambda x: self.to_metal(x["currencies"], self.pricelist.key_price["sell"]))
        # Remove blocked attributes by their defindex
        for listing in buy_listings:
            if "attributes" in listing["item"]:
                for attribute in listing["item"]["attributes"]:
                    for blocked_attribute in self.blocked_attributes:
                        if str(attribute["defindex"]) == str(self.blocked_attributes[blocked_attribute]):
                            buy_listings.remove(listing)
        for listing in sell_listings:
            if "attributes" in listing["item"]:
                for attribute in listing["item"]["attributes"]:
                    for blocked_attribute in self.blocked_attributes:
                        if str(attribute["defindex"]) == str(self.blocked_attributes[blocked_attribute]):
                            sell_listings.remove(listing)
        # Also filter outliers (SOON)
        key_buy_price = self.pricelist.key_price["buy"]
        key_sell_price = self.pricelist.key_price["sell"]
        buy_price = { "keys": 0, "metal": 0 }
        sell_price = { "keys": 0, "metal": 0 }
        buy_metal = 0
        sell_metal = 0
        external_price = self.pricelist.get_external_price(sku) # Get the external price
        if len(buy_listings) < self.buy_listing_amount:
            raise Exception("Not enough buy listings to calculate from.")
        else:
            for index, listing in enumerate(buy_listings):
                if index == self.buy_listing_amount:
                    break
                if "keys" in listing["currencies"]:
                    buy_price["keys"] += listing["currencies"]["keys"]
                if "metal" in listing["currencies"]:
                    buy_price["metal"] += listing["currencies"]["metal"]
            buy_metal = self.get_right(self.to_metal(buy_price, key_buy_price) / self.buy_listing_amount)
        if len(sell_listings) < 1:
            raise Exception("Not enough sell listings to calculate from.")
        else:
            for index, listing in enumerate(sell_listings):
                if index == self.sell_listing_amount:
                    break
                if "keys" in listing["currencies"]:
                    sell_price["keys"] += listing["currencies"]["keys"]
                if "metal" in listing["currencies"]:
                    sell_price["metal"] += listing["currencies"]["metal"]
            sell_metal = self.get_right(self.to_metal(sell_price, key_sell_price) / self.sell_listing_amount)
        if buy_metal > sell_metal:
            raise Exception("Buy price is higher than the sell price.")
        if buy_metal == sell_metal: # Just going to raise an exception for now
            raise Exception("Buy price is the same as the sell price.")
        fallback_buy_metal = self.to_metal(external_price["buy"], key_buy_price)
        fallback_sell_metal = self.to_metal(external_price["sell"], key_sell_price)
        buy_difference = self.calculate_percentage_difference(fallback_buy_metal, buy_metal)
        sell_difference = self.calculate_percentage_difference(fallback_sell_metal, sell_metal)
        if buy_difference > self.max_percentage_differences["buy"]:
            raise Exception("Pricer is buying for too much.")
        if sell_difference < self.max_percentage_differences["sell"]:
            raise Exception("Pricer is selling for too little.")
        # We did it, yay
        return {
            "name": sku["name"],
            "sku": sku["sku"],
            "source": "nekopricer",
            "time": int(time()),
            "buy": self.to_currencies(buy_metal, key_buy_price),
            "sell": self.to_currencies(sell_metal, key_sell_price)
        }
    
    # Helper functions
    def calculate_percentage_difference(self, value1, value2):
        if value1 == 0:
            return 0 if value2 == 0 else 100  # Handle division by zero
        return ((value2 - value1) / abs(value1)) * 100
    def to_metal(self, currencies: dict, key_price: dict):
        metal = 0
        metal += currencies.get("keys", 0) * key_price["metal"]
        metal += currencies.get("metal", 0)
        return self.get_right(metal)
    def to_currencies(self, metal: int, key_price: dict):
        currencies = {}
        keys = metal // key_price["metal"]
        metal -= keys * key_price["metal"]
        currencies["keys"] = keys
        currencies["metal"] = self.get_right(metal)
        return currencies
    def get_right(self, v):
        i = floor(v)
        f = round((v - i) / 0.11)
        return round(i + (f == 9 or f * 0.11), 2)