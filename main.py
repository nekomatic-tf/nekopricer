# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from asyncio import run
from json import load, loads
from src.server import start
from src.storage import MinIOEngine
from minio import S3Error
from src.backpacktf import BackpackTF
from src.pricer import Pricer
from threading import Thread
from signal import SIGABRT

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
    engine = MinIOEngine(config=minio_config)

    item_list = engine.read_file("item_list.json")
    if (type(item_list) == S3Error):
        logger.warn("Creating item_list.json")
        engine.write_file("item_list.json", "{\"items\": []}")
        item_list = engine.read_file("item_list.json")
    item_list = loads(item_list)
    logger.info("Updated allowed items!")
    
    bptf_config = config["backpackTf"]
    mongo_config = config["mongo"]

    websocket = BackpackTF(
        mongo_uri=mongo_config["uri"],
        database_name=mongo_config["db"],
        collection_name=mongo_config["collection"],
        ws_uri=bptf_config["websocket"],
        bptf_token=bptf_config["accessToken"],
        prioritized_items=item_list["items"]
    )

    prices_tf_config = config["pricesTf"]

    pricer = Pricer(
        mongo_uri=mongo_config["uri"],
        database_name=mongo_config["db"],
        collection_name=mongo_config["collection"],
        storage_engine=engine,
        items=item_list["items"],
        schema_server_url=prices_tf_config["schemaServer"]
    )
    
    backpacktf_thread = Thread(target=websocket.start_websocket)
    server_thread = Thread(target=start, args=[config])

    #backpacktf_thread.start()
    server_thread.start()

    #backpacktf_thread.join()
    server_thread.join()

    #start(config) # Start the server

    #logger.debug("PROGRAM IS GOING DOWN NOW! !! FORCING PROCESS TO EXIT !!")
    #kill(getpid(), SIGABRT) # This is a very dirty way of killing the program, but its probably the only useful way.
    
if __name__ == "__main__":
    run(main())