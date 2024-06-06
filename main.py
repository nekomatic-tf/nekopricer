# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from asyncio import run
from json import load, loads
import src.server as server
from src.storage import MinIOEngine
from minio import S3Error
from src.backpacktf import BackpackTF
from threading import Thread, Event

async def main():
    logging.basicConfig(
        handlers=[
            logging.FileHandler('pricer.log'),
            logging.StreamHandler(sys.stdout)
        ],
        format="%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
        level=logging.DEBUG
    )
    logger = logging.getLogger(__name__)
    logger.debug("Logger started.")

    with open("config.json", "r") as f:
        config = load(f)
    
    minio_config = config["minio"]
    storage_engine = MinIOEngine(config=minio_config)

    item_list = storage_engine.read_file("item_list.json")
    if (type(item_list) == S3Error):
        logger.warn("Creating item_list.json")
        storage_engine.write_file("item_list.json", "{\"items\": []}")
        item_list = storage_engine.read_file("item_list.json")
    item_list = loads(item_list)
    logger.info("Updated allowed items!")
    
    bptf_config = config["backpacktf"]
    mongo_config = config["mongo"]

    event = Event()

    websocket = BackpackTF(
        mongo_uri=mongo_config["uri"],
        database_name=mongo_config["db"],
        collection_name=mongo_config["collection"],
        ws_uri=bptf_config["websocket"],
        bptf_token=bptf_config["accessToken"],
        prioritized_items=item_list["items"]
    )

    backpacktf_thread = Thread(target=websocket.start_websocket, args=[event])
    backpacktf_thread.start()
    
    server.start(config)
    event.set()

if __name__ == "__main__":
    run(main())