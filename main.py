# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from json import load
from src.backpacktf import BackpackTF
from threading import Thread
from flask import Flask, Response
from flask_socketio import SocketIO
from src.pricer import Pricer
from src.pricelist import Pricelist
from os import kill, getpid
from signal import SIGABRT

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

app = Flask(__name__)
socket_io = SocketIO(app)

bptf_config = config["backpackTf"]
ptf_config = config["pricesTf"]
mongo_config = config["mongo"]
interval_config = config["intervals"]

logger.debug("Initializing classes...")
pricelist = Pricelist(
    config,
    socket_io
)
pricer = Pricer(
    config,
    pricelist,
    socket_io
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

first_connect = True
# Socket notifications
@socket_io.on("connect")
def on_connect(socket):
    global first_connect
    logger.info(f"A new client connected to the socket: {socket}. (Should they be authenticated?)")
    if (first_connect == True):
        first_connect = False
        logger.info("This is the first connection, calling pricer.price_items()")
        Thread(target=pricer.price_items).start()
@socket_io.on("disconnect")
def on_disconnect():
    logger.info(f"A client disconnected, we didn't even get to say goodbye :(")
# Routes
@app.get("/items")
def get_items():
    return pricelist.pricelist

@app.get("/items/<sku>")
def get_item(sku: str):
    for item in pricelist.pricelist["items"]:
        if item["sku"] == sku:
            return item
    return Response(status=404)

logger.debug("Starting API server...")
app.run(
    host=config["host"],
    port=config["port"]
)

logger.warning("PROGRAM IS GOING DOWN NOW! !! FORCING PROCESS TO EXIT !!")
logger.info("Saving pricelist...")
pricelist.write_pricelist()
print("Goodbye.")
kill(getpid(), SIGABRT) # This is a very dirty way of killing the program, but its probably the only useful way.