from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from threading import Thread
from time import sleep
from requests import get


class Snapshots:
    logger = getLogger("Snapshots")

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.snapshot_times = dict()

        self.snapshot_worker_thread = Thread(target=self.snapshot_worker)
        self.snapshot_worker_thread.daemon = True

    def start(self):
        self.logger.debug("Starting snapshot worker...")
        self.snapshot_worker_thread.start()

    @staticmethod
    def reformat_event(payload: dict) -> dict:
        if not payload:
            return dict()

        return {
            "steamid": payload.get("steamid"),
            "currencies": payload.get("currencies"),
            "trade_offers_preferred": payload.get("offers"),
            "buy_out_only": payload.get("buyoutOnly"),
            "listed_at": payload.get("timestamp"),
            "bumped_at": payload.get("bump"),
            "intent": payload.get("intent"),
            "user_agent": payload.get("userAgent"),
            "item": payload.get("item"),
            "details": payload.get("details"),
            "only_buyout": payload.get("buyout", True),
        }

    def snapshot_worker(self):
        self.logger.warning("Performing one time refresh of all items.")
        item_names = [item["name"] for item in self.pricer.pricelist.item_list]
        total = len(item_names)
        completed = 0
        # Snapshot everything, once
        for item in item_names:
            try:
                self.update_snapshot(item)
                self.logger.info(f"({completed} / {total}) Refreshed snapshot for {item}")
                completed += 1
            except Exception as e:
                completed += 1
                self.logger.error(f"({completed} / {total}) Failed to refresh snapshot for {item}: {e}")
            sleep(1)
        sleep(1)

        while True:
            self.snapshot_times = self.pricer.database.get_all_snapshot_times()
            item_names = [item["name"] for item in self.pricer.pricelist.item_list]
            oldest_items = sorted(
                ((k, v) for k, v in self.snapshot_times.items() if k in item_names.copy()),
                key=lambda x: x[1],
            )
            oldest_items = [item[0] for item in oldest_items][:10]
            missing_items = [item for item in item_names if item not in set(self.snapshot_times)]
            oldest_items.extend(missing_items)

            for item in oldest_items:
                try:
                    self.update_snapshot(item)
                    self.logger.info(f"Refreshed snapshot for {item}")
                except Exception as e:
                    self.logger.error(f"Failed to refresh snapshot for {item}: {e}")
                sleep(1)
            sleep(1)

    def update_snapshot(self, item_name: str) -> None:
        response = get(
            url=f"{self.pricer.options.backpackTfSnapshotUrl}",
            params={
                "token": self.pricer.options.backpackTfAccessToken,
                "sku": item_name,
                "appid": "440",
            },
        )

        if response.status_code == 429:
            self.logger.warning("Recieved error code 429 from backpack.tf.")
            sleep(5)
            return

        if response.status_code != 200:
            raise Exception(f"Recieved status code {response.status_code}")
            return

        snapshot = response.json()

        if not snapshot:
            return

        listings = snapshot.get("listings")
        snapshot_time = snapshot.get("createdAt")

        if not listings or not snapshot_time:
            return

        operations = {"insert": list(), "delete": list()}

        for listing in listings:
            listing_data = self.reformat_event(listing)
            if not listing_data:
                continue

            operations["insert"].append(
                {
                    "name": item_name,
                    "intent": listing_data.get("intent"),
                    "steamid": listing_data.get("steamid"),
                    "listing_data": listing_data,
                }
            )

        self.pricer.database.delete_item(item_name)
        self.pricer.database.update_many(operations)
        self.pricer.database.update_snapshot_time(item_name, snapshot_time)
        self.snapshot_times[item_name] = snapshot_time
