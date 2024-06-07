# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from json import load
from src.storage import MinIOEngine
from src.backpacktf import BackpackTF
from threading import Thread
from flask import Flask, Response
from flask_socketio import SocketIO
from src.pricer import Pricer

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
minio_config = config["minio"]
interval_config = config["intervals"]

logger.debug("Starting storage engine...")
engine = MinIOEngine(minio_config)

logger.debug("Initializing classes...")
pricer = Pricer(
    mongo_uri=mongo_config["uri"],
    database_name=mongo_config["db"],
    collection_name=mongo_config["collection"],
    storage_engine=engine,
    schema_server_url=ptf_config["schemaServer"],
    socket_io=socket_io,
    pricing_interval=interval_config["price"],
    max_percentage_differences=config["maxPercentageDifferences"],
    excluded_steam_ids=config["excludedSteamIDs"],
    trusted_steam_ids=config["trustedSteamIDs"],
    excluded_listing_descriptions=config["excludedListingDescriptions"],
    blocked_attributes=config["blockedAttributes"]
)
backpacktf = BackpackTF(
    mongo_uri=mongo_config["uri"],
    database_name=mongo_config["db"],
    collection_name=mongo_config["collection"],
    ws_uri=bptf_config["websocket"],
    bptf_token=bptf_config["accessToken"],
    prioritized_items=pricer.items["items"]
)

logger.debug("Starting websocket...")
websocket_thread = Thread(target=backpacktf.start_websocket)
websocket_thread.start()

# Routes
@app.get("/items")
def get_items():
    return pricer.pricelist

@app.get("/items/<sku>")
def get_item(sku: str):
    for item in pricer.pricelist["items"]:
        if item["sku"] == sku:
            return item
    return Response(status=404)

logger.debug("Starting API server...")
app.run(
    host=config["host"],
    port=config["port"]
)