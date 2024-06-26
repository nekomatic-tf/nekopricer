from flask import Flask, Response
from flask_socketio import SocketIO
from src.pricelist import Pricelist
from src.pricer import Pricer
from.backpacktf import BackpackTF
import logging

app = Flask(__name__)
socket = SocketIO(app)
logger = logging.getLogger("API Server")

# Socket
@socket.on("connect")
def on_connect(socket):
    logger.info(f"A new client connected to the socket: {socket}. (Should they be authenticated?)")
    pricelist.emit_price(pricelist.key_price)
@socket.on("disconnect")
def on_disconnect():
    logger.info(f"A client disconnected, we didn't even get to say goodbye :(")
# Routes
@app.get("/items")
def get_items():
    logger.info(f"Got pricelist.")
    return pricelist.pricelist
@app.get("/items/<sku>")
def get_item(sku: str):
    for item in pricelist.pricelist["items"]:
        if item["sku"] == sku:
            return item
    logger.info(f"Got price for {sku}.")
    return Response(status=404)
@app.post("/items/<sku>")
def check_item(sku: str):
    try:
        sku = {
            "sku": sku,
            "name": pricelist.to_name(sku)
        }
        pricer.price_item(sku)
        logger.info(f"Checked price for {sku["name"]}/{sku["sku"]}.")
        return sku
    except Exception as e:
        logger.info(f"Failed to check price for {sku}: {e}")
        return Response(status=500)

def init(
        _config: dict,
        _pricelist: Pricelist,
        _pricer: Pricer,
        _backpacktf: BackpackTF
):
    logger.info("Initializing API server...")
    global pricelist
    global pricer
    global backpacktf
    pricelist = _pricelist
    pricer = _pricer
    backpacktf = _backpacktf
    app.run(
        _config["host"],
        _config["port"]
    )

