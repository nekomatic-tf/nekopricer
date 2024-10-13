# Nekopricer V3

from logging import getLogger
from ..library.minio import MinIO
from .options import Options
from .server import Server
from .tokens import Tokens
from .database import Database
from .pricelist import Pricelist
from .websocket import Websocket
from .snapshots import Snapshots
from ..library.currencies import Currencies
from time import time, sleep
from threading import Thread


class Pricer:
    logger = getLogger("Nekopricer V3")

    statistics: dict = {
        "total": 0,
        "remaining": 0,
        "custom": 0,
        "fallback": 0,
        "failed": 0,
    }
    prices: list = []

    def __init__(self, minio: MinIO):
        self.minio = minio

        self.options = Options(self)
        self.options.loadOptions()
        self.logger.debug("Loaded options.")

        self.price_items_thread = Thread(target=self.price_items_loop)
        self.price_items_thread.daemon = True

        self.database = Database(self)
        self.websocket = Websocket(self)
        self.pricelist = Pricelist(self)
        self.snapshots = Snapshots(self)
        self.tokens = Tokens(self)
        self.server = Server(self)

        self.logger.debug("Classes initialized.")

    def start(self):
        self.logger.info("Starting Pricer...")
        self.pricelist.start()
        self.tokens.read_tokens()
        self.snapshots.start()
        self.websocket.start()
        self.price_items_thread.start()
        self.server.start()

    def stop(self):
        self.logger.debug("Shutting down...")
        self.database.close_connection()

    def price_items_loop(self):
        delay = self.options.jsonOptions["intervals"]["price"]
        self.logger.debug(f"Pricing items again in {delay} seconds.")
        sleep(delay)
        self.price_items()
        self.price_items_loop()

    def price_items(self):
        self.statistics = {key: 0 for key in self.statistics}  # Clear all statistics
        try:
            self.pricelist.freeze_pricelist()  # Keep a state of the previous pricelist
            items = [item["name"] for item in self.pricelist.item_list]
            skus = self.pricelist.to_sku_bulk(items)
            self.statistics["total"] = len(skus)
            self.statistics["remaining"] = len(skus)
            items = [{"sku": sku, "name": name} for sku, name in zip(skus, items)]  # Create a compatable dict
            for item in items:
                try:
                    if item["sku"] == "5021;6":
                        self.statistics["remaining"] -= 1
                        self.statistics["fallback"] += 1
                        continue  # We don't price the key
                    price = self.calculate_price(item)
                    self.pricelist.update_price(price)
                    self.statistics["remaining"] -= 1
                    self.statistics["custom"] += 1
                    self.logger.info(
                        f"({self.statistics["custom"] + self.statistics["fallback"]} / {self.statistics["total"]}) Priced {item["name"]}/{item["sku"]} using pricer."
                    )
                except Exception as e:
                    self.logger.error(
                        f"({self.statistics["custom"] + self.statistics["fallback"]} / {self.statistics["total"]}) Failed to price {item["name"]}/{item["sku"]} using pricer: {e}"
                    )
                    try:
                        price = self.pricelist.get_external_price(item)
                        price["fallback"] = e.args[0]  # Reason for fallback
                        self.pricelist.update_price(price)
                        self.statistics["remaining"] -= 1
                        self.statistics["fallback"] += 1
                        self.logger.info(
                            f"({self.statistics["custom"] + self.statistics["fallback"]} / {self.statistics["total"]}) Priced {item["name"]}/{item["sku"]} using fallback."
                        )
                    except Exception as e:
                        self.logger.error(
                            f"({self.statistics["custom"] + self.statistics["fallback"]} / {self.statistics["total"]}) Failed to price {item["name"]}/{item["sku"]} using fallback: {e}"
                        )
                        self.statistics["remaining"] -= 1
                        self.statistics["failed"] += 1
            # Post pricing
            self.pricelist.write_pricelist()
            self.pricelist.emit_prices()
        except Exception as e:
            self.logger.error(f"Failed to price items: {e}")

    def price_item(self, item: dict):
        try:
            if item["sku"] == "5021;6" and self.options.jsonOptions["enforceKeyFallback"]:
                raise Exception("Forcing key price to fallback according to options.")
            item["name"] = self.pricelist.to_name(item["sku"])
            price = self.calculate_price(item)
            if item["sku"] == "5021;6":
                self.pricelist.key_price = price
            self.pricelist.update_price(price)
            self.pricelist.emit_price(price)
        except Exception as e:
            if not item["sku"] == "5021;6":
                self.logger.error(f"Failed to price {item["name"]}/{item["sku"]} using pricer: {e}")
            price = self.pricelist.get_external_price(item)
            if price is None:
                self.logger.error(f"Failed to price {item["name"]}/{item["sku"]} using fallback.")
            if item["sku"] == "5021;6":
                self.pricelist.key_price = price
            self.pricelist.update_price(price)
            self.pricelist.emit_price(price)
            self.logger.info(f"Priced {item["name"]}/{item["sku"]} using fallback.")

    def calculate_price(self, item: dict) -> dict:
        options = self.options.jsonOptions
        buy_listings = self.database.get_listings_by_intent(item["name"], "buy")
        sell_listings = self.database.get_listings_by_intent(item["name"], "sell")
        # Stage 1 - Filtering
        # 1. Remove excluded steam ids
        buy_listings = [listing for listing in buy_listings if listing["steamid"] not in options["excludedSteamIDs"]]
        sell_listings = [listing for listing in sell_listings if listing["steamid"] not in options["excludedSteamIDs"]]
        # 2. Remove humans
        if options["pricingOptions"]["onlyBots"]:  # Filter out humans or use humans if we don't have any bots
            buy_listings_filtered = [listing for listing in buy_listings if listing["user_agent"] is not None]
            sell_listings_filtered = [listing for listing in sell_listings if listing["user_agent"] is not None]
            # 2.5. Use humans if no bots were found
            if not len(buy_listings_filtered) == 0 and not options["pricingOptions"]["buyHumanFallback"]:
                buy_listings = buy_listings_filtered
            if not len(sell_listings_filtered) == 0 and not options["pricingOptions"]["sellHumanFallback"]:
                sell_listings = sell_listings_filtered
        # 3. Remove excluded listing descriptions
        buy_listings = [
            listing for listing in buy_listings if all(excluded not in listing["details"] for excluded in options["excludedListingDescriptions"])
        ]
        sell_listings = [
            listing for listing in sell_listings if all(excluded not in listing["details"] for excluded in options["excludedListingDescriptions"])
        ]
        # 4. Remove marketplace.tf listings
        buy_listings = [listing for listing in buy_listings if "usd" not in listing["currencies"]]
        sell_listings = [listing for listing in sell_listings if "usd" not in listing["currencies"]]
        # 5. Sort from lowest to high and highest to low
        buy_listings = sorted(
            buy_listings,
            key=lambda x: Currencies(x["currencies"]).toValue(self.pricelist.key_price["buy"]["metal"]),
            reverse=True,
        )
        sell_listings = sorted(
            sell_listings,
            key=lambda x: Currencies(x["currencies"]).toValue(self.pricelist.key_price["buy"]["metal"]),
        )
        # 6. Remove block attributes
        if item["name"] not in options["paints"]:
            bad_listings = []
            for listing in buy_listings:
                if "attributes" in listing["item"]:
                    for attribute in listing["item"]["attributes"]:
                        for blocked_attribute in options["blockedAttributes"]:
                            if str(attribute["defindex"]) == str(blocked_attribute["defindex"]):
                                bad_listings.append(listing)
            for listing in sell_listings:
                if "attributes" in listing["item"]:
                    for attribute in listing["item"]["attributes"]:
                        for blocked_attribute in options["blockedAttributes"]:
                            if str(attribute["defindex"]) == str(blocked_attribute["defindex"]):
                                bad_listings.append(listing)
            buy_listings = [listing for listing in buy_listings if listing not in bad_listings]
            sell_listings = [listing for listing in sell_listings if listing not in bad_listings]
        # Stage 2 - Listing length check
        if len(buy_listings) == 0:
            raise Exception("No buy listings were found.")
        if len(sell_listings) == 0:
            raise Exception("No sell listings were found.")
        if len(buy_listings) > options["pricingOptions"]["buyLimit"] and options["pricingOptions"]["buyLimitStrict"]:
            raise Exception("Not enough buy listings were found.")
        if len(sell_listings) > options["pricingOptions"]["sellLimit"] and options["pricingOptions"]["sellLimitStrict"]:
            raise Exception("Not enough sell listings were found.")
        # Stage 3 - Nekopricer Pipeline (Be gay, do crime)
        key_buy_price_metal = self.pricelist.key_price["buy"]["metal"]
        buy_scrap = 0
        sell_scrap = 0
        external_price = self.pricelist.get_external_price(item)
        strategy = {"type": "", "valid": False}
        if external_price is None:
            raise Exception("Failed to get external price.")
        # Cutting
        if options["pricingOptions"]["allowCutting"] and not strategy["valid"]:
            cut_buy = all(x["currencies"] == buy_listings[0]["currencies"] for x in buy_listings[: options["pricingOptions"]["buyLimit"]])
            cut_sell = all(x["currencies"] == sell_listings[0]["currencies"] for x in sell_listings[: options["pricingOptions"]["sellLimit"]])
            if cut_buy and cut_sell:
                buy_scrap = Currencies(buy_listings[0]["currencies"]).toValue(key_buy_price_metal)
                sell_scrap = Currencies(sell_listings[0]["currencies"]).toValue(key_buy_price_metal)
                if sell_scrap - buy_scrap > 2:
                    buy_scrap += 1
                    sell_scrap += 1
                    strategy["type"] = "cut"
                    strategy["valid"] = True
        # Non-strict cutting
        if options["pricingOptions"]["allowSnipping"] and not strategy["valid"]:
            buy_scrap = Currencies(buy_listings[0]["currencies"]).toValue(key_buy_price_metal)
            sell_scrap = Currencies(sell_listings[0]["currencies"]).toValue(key_buy_price_metal)
            if sell_scrap - buy_scrap > 2:
                buy_scrap += 1
                sell_scrap -= 1
                strategy["type"] = "snipping"
                strategy["valid"] = True
        # Matching
        if options["pricingOptions"]["allowMatching"] and not strategy["valid"]:
            if strategy["valid"]:
                raise Exception("im a piece of shit uwu")
            buy_scrap = Currencies(buy_listings[0]["currencies"]).toValue(key_buy_price_metal)
            sell_scrap = Currencies(sell_listings[0]["currencies"]).toValue(key_buy_price_metal)
            if not buy_scrap == sell_scrap and not buy_scrap > sell_scrap:
                strategy["type"] = "matching"
                strategy["valid"] = True
        # Rounding
        if options["pricingOptions"]["allowRounding"] and not strategy["valid"]:
            # Reset scraps to 0
            buy_scrap = 0
            sell_scrap = 0
            denominator = 0
            for index, listing in enumerate(buy_listings):
                if index == options["pricingOptions"]["buyLimit"]:
                    break
                denominator += 1
                buy_scrap += Currencies(listing["currencies"]).toValue(key_buy_price_metal)
            buy_scrap = Currencies.round(buy_scrap / denominator)
            denominator = 0
            for index, listing in enumerate(sell_listings):
                if index == options["pricingOptions"]["sellLimit"]:
                    break
                denominator += 1
                sell_scrap += Currencies(listing["currencies"]).toValue(key_buy_price_metal)
            sell_scrap = Currencies.round(sell_scrap / denominator)

            if not buy_scrap == sell_scrap and not buy_scrap > sell_scrap:
                strategy["type"] = "round"
                strategy["valid"] = True
        # Backing off
        if options["pricingOptions"]["allowBacking"] and not strategy["valid"]:
            buy_scrap = sell_scrap - 1
            strategy["type"] = "backoff"
            strategy["valid"] = True
        # Failed
        if not strategy["valid"]:
            strategy["type"] = "fallback"
            self.logger.debug("NetBurst pipeline completed with a failure to validate any method of pricing.")
            self.logger.warning(f"Failed to validate a strategy to price {item["name"]}/{item["sku"]}.")

        # If value is above {scrap} refined, don't use halfscrap
        if buy_scrap >= 9 and not buy_scrap.is_integer():
            buy_scrap -= 0.5
        if sell_scrap >= 9 and not sell_scrap.is_integer():
            sell_scrap += 0.5

        # Stage 4 - Safety checks
        if buy_scrap > sell_scrap:
            raise Exception("Buy price is higher than the sell price.")
        if buy_scrap == sell_scrap:
            raise Exception("Buy price is the same as the sell price.")
        if buy_scrap == 0:
            raise Exception("Buy price cannot be zero.")
        if sell_scrap == 0:
            raise Exception("Sell price cannot be zero.")
        if buy_scrap < 0:
            raise Exception("Buy price cannot be negative.")
        if sell_scrap < 0:
            raise Exception("Sell price cannot be negative.")
        currencies = {}
        currencies["buy"] = Currencies.toCurrencies(buy_scrap, None)
        currencies["sell"] = Currencies.toCurrencies(sell_scrap, None)
        if currencies["buy"] == currencies["sell"]:
            raise Exception("Buy price is the same as the sell price after conversion to refined.")
        if not item["sku"] == "5021;6":  # Skip over the key
            currencies["buy"] = Currencies.toCurrencies(buy_scrap, key_buy_price_metal)
            currencies["sell"] = Currencies.toCurrencies(sell_scrap, key_buy_price_metal)
        if currencies["buy"] == currencies["sell"]:
            raise Exception("Buy price is the same as the sell price after conversion to currencies.")
        if Currencies(currencies["buy"]).toValue(key_buy_price_metal) == Currencies(currencies["sell"]).toValue(key_buy_price_metal):
            raise Exception("Buy price is the same as the sell price after conversion back to scrap.")
        if Currencies(currencies["buy"]).toValue(key_buy_price_metal) > Currencies(currencies["sell"]).toValue(key_buy_price_metal):
            raise Exception("Buy price is higher than the sell price after conversion back to scrap.")
        if currencies["buy"]["keys"] == currencies["sell"]["keys"] and currencies["buy"]["metal"] > currencies["sell"]["metal"]:
            raise Exception("Buy price is higher than the sell price after a post conversion check.")
        # Stage 3 - Baselines
        fallback_buy_scrap = Currencies(external_price["buy"]).toValue(key_buy_price_metal)
        fallback_sell_scrap = Currencies(external_price["sell"]).toValue(key_buy_price_metal)
        buy_difference = self.calculate_percentage_difference(fallback_buy_scrap, buy_scrap)
        sell_difference = self.calculate_percentage_difference(fallback_sell_scrap, sell_scrap)
        if buy_difference > self.options.jsonOptions["maxPercentageDifferences"]["buy"]:
            raise Exception("Pricer is buying for too much.")
        if sell_difference < self.options.jsonOptions["maxPercentageDifferences"]["sell"]:
            raise Exception("Pricer is selling for too little.")

        return {
            "name": item["name"],
            "sku": item["sku"],
            "source": "nekopricer",
            "time": int(time()),
            "buy": currencies["buy"],
            "sell": currencies["sell"],
            "strategy": strategy,
        }

    def calculate_percentage_difference(self, value1, value2):
        if value1 == 0:
            return 0 if value2 == 0 else 100  # Handle division by zero
        return ((value2 - value1) / abs(value1)) * 100
