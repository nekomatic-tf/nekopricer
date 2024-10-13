from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from asyncio import Future, create_task, sleep, run
from websockets import (
    connect,
    ConnectionClosedError,
    ConnectionClosedOK,
    ConnectionClosed,
)
from json import loads
from threading import Thread
from time import time


class Websocket:
    logger = getLogger("Websocket")

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.websocket_thread = Thread(target=lambda: run(self.start_websocket()))
        self.websocket_thread.daemon = True

    def start(self):
        self.logger.debug("Starting websocket client...")
        self.websocket_thread.start()

    @staticmethod
    async def reformat_event(payload: dict) -> dict:
        if not payload:
            return dict()

        return {
            "steamid": payload.get("steamid"),
            "currencies": payload.get("currencies"),
            "trade_offers_preferred": payload.get("tradeOffersPreferred"),
            "buy_out_only": payload.get("buyoutOnly"),
            "listed_at": payload.get("listedAt"),
            "bumped_at": payload.get("bumpedAt"),
            "intent": payload.get("intent"),
            "user_agent": payload.get("userAgent"),
            "item": payload.get("item"),
            "details": payload.get("details"),
            "only_buyout": payload.get("buyout", True),
        }

    async def start_websocket(self):
        self.pricer.database.delete_old_listings(172800 + time())  # 2 days

        # Create index on name
        self.pricer.database.create_index()

        while True:
            try:
                async with connect(
                    uri=self.pricer.options.backpackTfWebsocketUrl,
                    max_size=None,
                    ping_interval=60,
                    ping_timeout=120,
                ) as websocket:
                    await self.handle_websocket(websocket)
                    await Future()
            except (ConnectionClosedError, ConnectionClosedOK, ConnectionClosed) as e:
                self.logger.error(f"Websocket connection closed: {e}")
                self.logger.debug("Attempting to reconnect in 3 seconds...")
                await sleep(3)
            except KeyboardInterrupt:
                break

    async def handle_websocket(self, websocket):
        self.logger.info("Connected to backpack.tf websocket!")
        listing_count = 0

        async for message in websocket:
            self.logger.debug(f"Collected {listing_count} total events.")

            json_data = loads(message)

            if isinstance(json_data, list):
                create_task(self.handle_list_events(json_data))
                self.logger.info(f"Recieved {len(json_data)} events.")
                listing_count += len(json_data)
            else:
                create_task(self.handle_event(json_data, json_data.get("event")))
                self.logger.info("Recieved 1 event.")
                listing_count += 1
        return

    async def handle_event(self, data: dict, event: str):
        # If no data is provided, exit the function
        if not data:
            return

        item_name = data.get("item", dict()).get("name")
        # Don't save an item that isn't in our item list
        item_names = [item["name"] for item in self.pricer.pricelist.item_list]
        if item_name not in item_names:
            return

        # Depending on the event type, perform different actions
        match event:
            # If the event is a listing update
            case "listing-update":
                # Process the listing
                await self.process_listing(data, item_name)

            # If the event is a listing deletion
            case "listing-delete":
                # Process the deletion
                await self.process_deletion(item_name, data.get("intent"), data.get("steamid"))

            # If the event is neither a listing update nor a deletion, exit the function
            case _:
                return
        return

    async def handle_list_events(self, events: list):
        listings_to_update = {"insert": list(), "delete": list()}
        for event in events:
            data = event.get("payload", dict())
            item_name = data.get("item", dict()).get("name")

            # Don't add this item if its not in our item list
            item_names = [item["name"] for item in self.pricer.pricelist.item_list]
            if item_name not in item_names:
                continue

            if not data:
                continue

            match event.get("event"):
                case "listing-update":
                    listing_data = await self.reformat_event(data)
                    if not listing_data:
                        continue

                    listings_to_update["insert"].append(
                        {
                            "name": item_name,
                            "intent": listing_data.get("intent"),
                            "steamid": listing_data.get("steamid"),
                            "listing_data": listing_data,
                        }
                    )
                    self.logger.debug(
                        f"listing-update for {item_name} with intent {listing_data.get('intent')}" f" and steamid {listing_data.get('steamid')}"
                    )

                case "listing-delete":
                    listings_to_update["delete"].append(
                        {
                            "name": item_name,
                            "intent": data.get("intent"),
                            "steamid": data.get("steamid"),
                        }
                    )
                    self.logger.debug(f"listing-delete for {item_name} with intent {data.get("intent")}" f" and steamid {data.get("steamid")}")

                case _:
                    continue
        self.pricer.database.update_many(listings_to_update)

    async def process_listing(self, data: dict, item_name: str) -> None:
        # Reformat the data
        listing_data = await self.reformat_event(data)
        # If the data is empty, exit the function
        if not listing_data:
            return

        # Insert the listing into the database
        await self.pricer.database.insert_listing(
            item_name,
            listing_data.get("intent"),
            listing_data.get("steamid"),
            listing_data,
        )
        self.logger.debug(f"listing-update for {item_name} with intent {listing_data.get('intent')}" f" and steamid {listing_data.get('steamid')}")

    async def process_deletion(self, item_name: str, intent: str, steamid: str) -> None:
        # Delete the listing from the database
        await self.pricer.database.delete_listing(item_name, intent, steamid)
        self.logger.debug(f"listing-delete for {item_name} with intent {intent} and steamid {steamid}")
