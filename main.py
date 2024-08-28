# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import colorlog
import sys
from json import load
from src.backpacktf import BackpackTF
from threading import Thread
from src.pricer import Pricer
from src.pricelist import Pricelist
from os import kill, getpid
from asyncio import run
from src.server.server import init, socket
from signal import signal, SIGINT, SIGABRT, SIGTERM
from src.storage import S3Engine

logging_console_handler = colorlog.StreamHandler()
logging_console_handler.setFormatter(colorlog.ColoredFormatter("[ %(asctime)s ] [ %(log_color)s%(levelname)s%(reset)s ] [ %(name)s ]: %(message)s"))
logging_file_handler = logging.FileHandler("app.log")
logging_file_handler.setFormatter(logging.Formatter("[ %(asctime)s ] [ %(levelname)s ] [ %(name)s ]: %(message)s"))

logging.basicConfig(
    handlers=[
        logging_console_handler,
        logging_file_handler
    ],
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

s3engine = S3Engine(config["minio"])

pricelist = Pricelist(
    config,
    socket,
    s3engine
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
    pricelist=pricelist
)

logger.debug("Starting websocket...")
websocket_thread = Thread(target=backpacktf.start_websocket)
websocket_thread.start()

#pricer.price_items()

def shutdown(sig, frame):
    logger.warning("Shutting down...")
    logger.info("Shutting database down...")
    run(backpacktf.close_connection())
    # "stop" server idk
    print("Goodbye :(")
    kill(getpid(), SIGABRT)

signal(SIGINT, shutdown)
signal(SIGTERM, shutdown)

init(
    _config=config,
    _pricelist=pricelist,
    _pricer=pricer,
    _backpacktf=backpacktf,
    _s3engine=s3engine
)