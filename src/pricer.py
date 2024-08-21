# Pricer pricelist helper

import logging
from src.database import ListingDBManager
from asyncio import new_event_loop
from src.helpers import set_interval_and_wait, set_interval, PricerException
from src.pricelist import Pricelist
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
        self.only_use_bots = config["pricingTolerances"]["onlyBots"]
        self.undercut = config["pricingTolerances"]["undercut"]
        self.overcut = config["pricingTolerances"]["overcut"]
        self.buy_limit = config["pricingTolerances"]["buyLimit"]
        self.sell_limit = config["pricingTolerances"]["sellLimit"]
        self.buy_limit_strict = config["pricingTolerances"]["buyLimitStrict"]
        self.sell_limit_strict = config["pricingTolerances"]["sellLimitStrict"]
        self.buy_human_fallback = config["pricingTolerances"]["buyHumanFallback"]
        self.sell_human_fallback = config["pricingTolerances"]["sellHumanFallback"]
        self.partial_fallback = config["pricingTolerances"]["partialFallback"]
        self.enforce_key_fallback = config["enforceKeyFallback"]
        self.paints = config["paints"]
        self.pricelist = pricelist
        self.event_loop = new_event_loop()
        self.statistics = {
            "total": 0,
            "remaining": 0,
            "custom": 0,
            "pricestf": 0,
            "failed": 0
        }
        if not self.enforce_key_fallback == True: # We are allowed to natively price the key, pricelist won't price key for us
            self.logger.info("Key will be priced using the pricer.")
            set_interval(self.get_key_price, config["intervals"]["key"])
        set_interval_and_wait(self.price_items, self.price_interval)
        return

    def price_items(self):
        # Get all the SKUs
        self.statistics = {key: 0 for key in self.statistics} # Clear all statistics
        try:
            items = []
            for item in self.pricelist.item_list["items"]:
                items.append(item["name"])
            skus = self.pricelist.to_sku_bulk(items)
            self.statistics["total"] = len(skus)
            self.statistics["remaining"] = self.statistics["total"]
            skus = [{"sku": sku, "name": name} for sku, name in zip(skus, items)] # Produce a reasonable format iterate
            for sku in skus:
                try:
                    if sku["sku"] == "5021;6":     
                        self.statistics["remaining"] -= 1
                        self.statistics["pricestf"] += 1
                        continue # We don't price the key
                    price = self.calculate_price(sku) # Attempt to price this specific item (will throw an exception if it fails)
                    self.pricelist.update_price(price)
                    self.statistics["remaining"] -= 1
                    self.statistics["custom"] += 1
                    self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using pricer.")
                except PricerException as e:
                    self.logger.error(f"Failed to price item {sku["name"]}/{sku["sku"]} using pricer: {e}")
                    try:
                        price = self.pricelist.get_external_price(sku)
                        price["fallback"] = e.get_data()
                        self.pricelist.update_price(price)
                        self.statistics["remaining"] -= 1
                        self.statistics["pricestf"] += 1
                        self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using fallback.")
                    except Exception as e:
                        self.logger.error(f"Failed to price {sku["name"]}/{sku["sku"]} using fallback: {e}")
                        print("!! THIS IS VERY BAD CHECK CODE !!")
                        self.statistics["failed"] += 1
                        self.statistics["remaining"] -= 1
                self.logger.info(f"\nTotal:     {self.statistics["total"]}\nRemaining: {self.statistics["remaining"]}\nCustom:    {self.statistics["custom"]}\nPrices.TF: {self.statistics["pricestf"]}\nFailed:    {self.statistics["failed"]}")
            self.pricelist.emit_prices()
            self.logger.info(f"\nDONE\nTotal:     {self.statistics["total"]}\nRemaining: {self.statistics["remaining"]}\nCustom:    {self.statistics["custom"]}\nPrices.TF: {self.statistics["pricestf"]}\nFailed:    {self.statistics["failed"]}")
            self.logger.info(f"Sleeping for {self.price_interval} seconds (If this is the interval loop).")
        except Exception as e:
            self.logger.error(e)
    
    # NOTE: This function won't do any IO as its not meant to be the main pricer function, its just meant to price one,
    # and update said item in the pricelist, it doesn't fetch the array or anything, no need to (and the main function might remove that too)
    def price_item(self, sku: dict): # Simply prices and emits a new price for a single item, and ignores the whitelist
        try:
            sku["name"] = self.pricelist.to_name(sku["sku"])
            try:
                if sku["sku"] == "5021;6" and self.enforce_key_fallback == True: # Enforce fallback for the key if SKU is a key.
                    raise Exception("Key pricing is disabled.")
                price = self.calculate_price(sku)
                if sku["sku"] == "5021;6": # What the FUCK is this? (Answer: Key pricing code)
                    price = self.format_key(price)
                    self.pricelist.key_price = price
                self.pricelist.update_price(price)
                self.pricelist.emit_price(price)
                self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using pricer.")
            except PricerException as e:
                self.logger.error(f"Failed to price item {sku["name"]}/{sku["sku"]} using pricer: {e}")
                try:
                    price = self.pricelist.get_external_price(sku)
                    price["fallback"] = e.get_data()
                    self.pricelist.update_price(price)
                    self.pricelist.emit_price(price)
                    self.logger.info(f"Priced item {sku["name"]}/{sku["sku"]} using fallback.")
                except Exception as e:
                    self.logger.error(f"Failed to price {sku["name"]}/{sku["sku"]} using fallback: {e}")
                    print("!! THIS IS VERY BAD CHECK CODE !!")
        except Exception as e:
            self.logger.error(e)
    def get_key_price(self): # Native pricer version (see pricelist.py for external API version)
        self.price_item({
            "sku": "5021;6",
            "name": "Mann Co. Supply Crate Key"
        })
        self.logger.info("Refreshed price for Mann Co. Supply Crate Key/5021;6.")
        
    def calculate_price(self, sku: dict):
        buy_listings = self.event_loop.run_until_complete(self.database.get_listings_by_intent(sku["name"], "buy"))
        sell_listings = self.event_loop.run_until_complete(self.database.get_listings_by_intent(sku["name"], "sell"))
        # Perform a series of filtering before making sure we have enough listings
        # Filter out excluded steam ids
        buy_listings = [listing for listing in buy_listings if listing["steamid"] not in self.excluded_steam_ids]
        sell_listings = [listing for listing in sell_listings if listing["steamid"] not in self.excluded_steam_ids]
        if self.only_use_bots == True: # Filter out listings without a user agent    
            buy_listings_filtered = [listing for listing in buy_listings if listing["user_agent"] is not None]
            sell_listings_filtered = [listing for listing in sell_listings if listing["user_agent"] is not None]
            if self.buy_human_fallback == True:
                if not len(buy_listings_filtered) == 0:
                    buy_listings = buy_listings_filtered
            else:
                buy_listings = buy_listings_filtered
            if self.sell_human_fallback == True:
                if not len(sell_listings_filtered) == 0:
                    sell_listings = sell_listings_filtered
            else:
                sell_listings = sell_listings_filtered
        # Filter out excluded listing descriptions
        buy_listings = [listing for listing in buy_listings if all(excluded not in listing["details"] for excluded in self.excluded_listing_descriptions)]
        sell_listings = [listing for listing in sell_listings if all(excluded not in listing["details"] for excluded in self.excluded_listing_descriptions)]
        # Filter out marketplace.tf listings
        buy_listings = [listing for listing in buy_listings if "usd" not in listing["currencies"]]
        sell_listings = [listing for listing in sell_listings if "usd" not in listing["currencies"]]
        # Sort from lowest to high and highest to low
        buy_listings = sorted(buy_listings, key=lambda x: self.to_halfscrap(x["currencies"], self.pricelist.key_price["buy"]), reverse=True)
        sell_listings = sorted(sell_listings, key=lambda x: self.to_halfscrap(x["currencies"], self.pricelist.key_price["sell"]))
        # Remove blocked attributes by their defindex (if they aren't a paint)
        if not sku["name"] in self.paints:
            bad_listings = []
            for listing in buy_listings:
                if "attributes" in listing["item"]:
                    for attribute in listing["item"]["attributes"]:
                        for blocked_attribute in self.blocked_attributes:
                            if str(attribute["defindex"]) == str(blocked_attribute["defindex"]):
                                bad_listings.append(listing)
            for listing in sell_listings:
                if "attributes" in listing["item"]:
                    for attribute in listing["item"]["attributes"]:
                        for blocked_attribute in self.blocked_attributes:
                            if str(attribute["defindex"]) == str(blocked_attribute["defindex"]):
                                bad_listings.append(listing)
            buy_listings = [listing for listing in buy_listings if listing not in bad_listings]
            sell_listings = [listing for listing in sell_listings if listing not in bad_listings]
        # Make sure we have enough listings to do some math
        if len(buy_listings) == 0:
            raise PricerException({
                "reason": "No buy listings were found."
            })
        if len(sell_listings) == 0:
            raise PricerException({
                "reason": "No sell listings were found."
            })
        # Also filter outliers (SOON)
        key_buy_price = self.pricelist.key_price["buy"]
        key_sell_price = self.pricelist.key_price["sell"]
        buy_price = { "keys": 0, "metal": 0 }
        sell_price = { "keys": 0, "metal": 0 }
        buy_halfscrap = 0
        sell_halfscrap = 0
        external_price = self.pricelist.get_external_price(sku) # Get the external price
        '''
        Nekopricer Documentation / rant
        Limits:
        -1 - Pricer will undercut or overcut the lowest listing, or potentially an offset listing (outlier shit)
        0 - Pricer will match the first buy and sell listing
        1 - Pricer will match the first buy and sell listing (as well as calculate average?(pointless))
        2+ - Pricer will get an average from the amount of buy and sell listings
        limit_strict: True - Pricer needs to the desired amount of listings to price
        limit_strict: False - Pricer can price using less than the desired amount of listings
        '''
        if len(buy_listings) < self.buy_limit and self.buy_limit_strict == True:
            raise PricerException({
                "reason": "Not enough buy listings to calculate from."
            })
        else:
            denominator = 0
            for index, listing in enumerate(buy_listings):
                if index == self.buy_limit:
                    break
                denominator += 1
                if "keys" in listing["currencies"]:
                    buy_price["keys"] += listing["currencies"]["keys"]
                if "metal" in listing["currencies"]:
                    buy_price["metal"] += listing["currencies"]["metal"]
            buy_halfscrap = round(self.to_halfscrap(buy_price, key_buy_price) / denominator)
        if len(sell_listings) < self.sell_limit and self.sell_limit_strict == True:
            raise PricerException({
                "reason": "Not enough sell listings to calculate from."
            })
        else:
            denominator = 0
            for index, listing in enumerate(sell_listings):
                if index == self.sell_limit:
                    break
                denominator += 1
                if "keys" in listing["currencies"]:
                    sell_price["keys"] += listing["currencies"]["keys"]
                if "metal" in listing["currencies"]:
                    sell_price["metal"] += listing["currencies"]["metal"]
            sell_halfscrap = round(self.to_halfscrap(sell_price, key_sell_price) / denominator)
        if buy_halfscrap > sell_halfscrap:
            raise PricerException({
                "reason": "Buy price is higher than the sell price."
            })
        if buy_halfscrap == sell_halfscrap: # Just going to raise an exception for now
            raise PricerException({
                "reason": "Buy price is the same as the sell price."
            })
        if buy_halfscrap == 0:
            raise PricerException({
                "reason": "Buy price cannot be zero."
            })
        if sell_halfscrap == 0:
            raise PricerException({
                "reason": "Sell price cannot be zero."
            })
        fallback_buy_halfscrap = self.to_halfscrap(external_price["buy"], key_buy_price)
        fallback_sell_halfscrap = self.to_halfscrap(external_price["sell"], key_sell_price)
        buy_difference = self.calculate_percentage_difference(fallback_buy_halfscrap, buy_halfscrap)
        sell_difference = self.calculate_percentage_difference(fallback_sell_halfscrap, sell_halfscrap)
        if buy_difference > self.max_percentage_differences["buy"]:
            raise PricerException({
                "reason": "Pricer is buying for too much."
            })
        if sell_difference < self.max_percentage_differences["sell"]:
            raise PricerException({
                "reason": "Pricer is selling for too little."
            })
        currencies = {
            "buy": self.to_currencies(buy_halfscrap, key_buy_price),
            "sell": self.to_currencies(sell_halfscrap, key_sell_price)
        }
        if (currencies["buy"] == currencies["sell"]):
            raise PricerException({
                "reason": "Buy price is the same as the sell price after conversion."
            })
        # We did it, yay
        return {
            "name": sku["name"],
            "sku": sku["sku"],
            "source": "nekopricer",
            "time": int(time()),
            "buy": currencies["buy"],
            "sell": currencies["sell"]
        }
    
    # Helper functions
    def format_key(self, price: dict): # Convert the key to pure metal (Only during native pricing)
        ## ALERT ALERT LEGACY CODE DO NOT TOUCH ##
        price["buy"]["metal"] = self.to_metal(price["buy"], self.pricelist.key_price["buy"])
        price["sell"]["metal"] = self.to_metal(price["sell"], self.pricelist.key_price["sell"])
        price["buy"]["keys"] = 0
        price["sell"]["keys"] = 0
        return price
    def calculate_percentage_difference(self, value1, value2):
        if value1 == 0:
            return 0 if value2 == 0 else 100  # Handle division by zero
        return ((value2 - value1) / abs(value1)) * 100
    def to_metal(self, currencies: dict, key_price: dict):
        metal = 0
        metal += currencies.get("keys", 0) * key_price["metal"]
        metal += currencies.get("metal", 0)
        return self.get_right(metal)
    def to_halfscrap(self, currencies: dict, key_price: dict): # Convert to our beloved halfscrap
        halfscrap = 0
        halfscrap += currencies.get("keys", 0) * round(key_price["metal"] * 18)
        halfscrap += round(currencies.get("metal", 0) * 18)
        return halfscrap
    # Legacy Code (DO NOT TOUCH)
    """def to_currencies(self, metal: int, key_price: dict):
        currencies = {}
        keys = metal // key_price["metal"]
        metal -= keys * key_price["metal"]
        currencies["keys"] = keys
        currencies["metal"] = self.get_right(metal)
        return currencies"""
    
    def to_currencies(self, halfscrap: int, key_price: dict):
        currencies = {}
        currencies["keys"] = round(halfscrap // round(key_price["metal"] * 18))
        # Keeping this for my sanity
        #halfscrap -= currencies["keys"] * round(key_price["metal"] * 18)
        currencies["metal"] = float(f"{(halfscrap - currencies['keys'] * round(key_price['metal'] * 18)) / 18:.2f}")
        # Run a get right so it doesn't cut by 0.05 that is NOT something we want
        currencies["metal"] = self.get_right(currencies["metal"])
        return currencies
    def get_right(self, v):
        i = floor(v)
        f = round((v - i) / 0.11)
        return round(i + (f == 9 or f * 0.11), 2)