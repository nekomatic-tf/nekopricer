# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from json import load
from src.storage import MinIOEngine
from src.backpacktf import BackpackTF
from threading import Thread
from flask import Flask
from flask_socketio import SocketIO
from src.pricer import Pricer

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

app = Flask(__name__)
socket_io = SocketIO(app)

bptf_config = config["backpackTf"]
ptf_config = config["pricesTf"]
mongo_config = config["mongo"]
minio_config = config["minio"]

logger.debug("Starting storage engine...")
engine = MinIOEngine(minio_config)

logger.debug("Initializing classes...")
pricer = Pricer(
    mongo_uri=mongo_config["uri"],
    database_name=mongo_config["db"],
    collection_name=mongo_config["collection"],
    storage_engine=engine,
    schema_server_url=ptf_config["schemaServer"],
    socket_io=socket_io
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
#websocket_thread.start()

logger.debug("Starting API server...")
app.run(
    host=config["host"],
    port=config["port"]
)