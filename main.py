# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from json import load
from src.backpacktf import BackpackTF
from threading import Thread
from src.pricer import Pricer
from src.pricelist import Pricelist
from os import kill, getpid
from signal import SIGABRT
from asyncio import run
from src.server import init, socket

logging.basicConfig(
    handlers=[
        logging.FileHandler('pricer.log'),
        logging.StreamHandler(sys.stdout)
    ],
    format="%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.debug("Logger started.")

with open("config.json", "r") as f:
    config = load(f)

bptf_config = config["backpackTf"]
ptf_config = config["pricesTf"]
mongo_config = config["mongo"]
interval_config = config["intervals"]

logger.debug("Initializing classes...")
pricelist = Pricelist(
    config,
    socket
)
pricer = Pricer(
    config,
    pricelist
)
backpacktf = BackpackTF(
    mongo_uri=mongo_config["uri"],
    database_name=mongo_config["db"],
    collection_name=mongo_config["collection"],
    ws_uri=bptf_config["websocket"],
    bptf_token=bptf_config["accessToken"],
    prioritized_items=pricelist.item_list
)

logger.debug("Starting websocket...")
websocket_thread = Thread(target=backpacktf.start_websocket)
#websocket_thread.start()

pricer.price_items()

init(
    host=config["host"],
    port=config["port"],
    _pricelist=pricelist,
    _pricer=pricer
)

logger.warning("PROGRAM IS GOING DOWN NOW! !! FORCING PROCESS TO EXIT !!")
logger.info("Saving pricelist...")
pricelist.write_pricelist()
logger.info("Shutting backpacktf database down...")
run(backpacktf.close_connection())
print("Goodbye.")
kill(getpid(), SIGABRT) # This is a very dirty way of killing the program, but its probably the only useful way.