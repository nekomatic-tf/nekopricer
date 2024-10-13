from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from pymongo import MongoClient, UpdateOne


class Database:
    logger = getLogger("Database")

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.client = MongoClient(self.pricer.options.mongoUri)
        self.database = self.client[self.pricer.options.mongoDb]
        self.collection = self.database[self.pricer.options.mongoCollection]

    def create_index(self):
        self.collection.create_index([("name", 1)], unique=True)

    def insert_listing(self, name: str, intent: str, steamid: str, listing_data: dict):
        self.delete_listing(name, intent, steamid)
        self.collection.update_one(
            {"name": name},
            {"$push": {"listings": listing_data}, "$setOnInsert": {"name": name}},
            upsert=True,
        )

    def delete_listing(self, name: str, intent: str, steamid: str):
        self.collection.update_one(
            {"name": name},
            {"$pull": {"listings": {"steamid": steamid, "intent": intent}}},
        )  # Remove the listing from the document, if it exists

    def update_many(self, listings_to_update: dict):
        insert_listings = listings_to_update.get("insert", [])
        delete_listings = listings_to_update.get("delete", [])

        delete_bulk = list()
        insert_bulk = list()

        for operation in insert_listings:
            delete_bulk.append(
                UpdateOne(
                    {"name": operation["name"]},
                    {
                        "$pull": {
                            "listings": {"steamid": operation["steamid"]},
                            "intent": operation["intent"],
                        }
                    },
                )
            )
            insert_bulk.append(
                UpdateOne(
                    {"name": operation["name"]},
                    {
                        "$addToSet": {"listings": operation["listing_data"]},
                        "$setOnInsert": {"name": operation["name"]},
                    },
                    upsert=True,
                )
            )

        for operation in delete_listings:
            delete_bulk.append(
                UpdateOne(
                    {"name": operation["name"]},
                    {
                        "$pull": {
                            "listings": {
                                "steamid": operation["steamid"],
                                "intent": operation["intent"],
                            }
                        }
                    },
                )
            )

        self.collection.bulk_write(delete_bulk) if delete_bulk else None
        self.collection.bulk_write(insert_bulk) if insert_bulk else None

    def update_snapshot_time(self, name: str, snapshot_time: float):
        self.collection.update_one({"name": name}, {"$set": {"snapshot_time": snapshot_time}})

    def get_snapshot_time(self, name: str) -> float:
        snapshot_time = self.collection.find_one({"name": name}, {"snapshot_time": 1})
        return snapshot_time.get("snapshot_time") if snapshot_time else 0

    def get_all_snapshot_times(self) -> dict:
        cursor = self.collection.find({}, {"_id": 0, "name": 1, "snapshot_time": 1})
        snapshot_times = {}
        for document in cursor:
            snapshot_times[document["name"]] = document.get("snapshot_time", 0)
        return snapshot_times

    def delete_old_listings(self, max_time: float):
        self.collection.update_many(
            {},
            [
                {
                    "$set": {
                        "listings": {
                            "$filter": {
                                "input": "$listings",
                                "cond": {"$gte": ["$$this.updated", max_time]},
                            }
                        }
                    }
                }
            ],
        )

    def delete_item(self, name: str):
        self.collection.delete_one({"name": name})

    # "Does this trash even work?"
    # This trash does indeed work :3
    def get_listings_by_intent(self, name: str, intent: str) -> list:
        result = self.collection.find_one({"name": name})
        if result:
            filtered_listings = [listing for listing in result["listings"] if listing["intent"] == intent]
            return filtered_listings
        return []

    def get_listings(self, name: str) -> list:
        result = self.collection.find_one({"name": name})
        if result:
            return result["listings"]
        return []

    def close_connection(self):
        self.client.close()
