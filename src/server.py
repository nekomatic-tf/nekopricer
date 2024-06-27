from flask import Flask, Response
from flask_socketio import SocketIO
from src.pricelist import Pricelist
from src.pricer import Pricer
from.backpacktf import BackpackTF
import logging
from asyncio import new_event_loop

event_loop = new_event_loop()
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
    price = pricelist.get_price(sku)
    if not price == None:
        return price
    # Item doesn't exist, add and price
    try:
        pricer.price_item({
            "sku": sku,
            "name": pricelist.to_name(sku)
        })
        price = pricelist.get_price(sku)
        if not price == None: # Item is now priced, and added to the item_list, ready to roll
            pricelist.add_item(price["name"])
            return price 
        return Response(status=404) # Failed to price etc etc
    except Exception as e:
        logger.error(f"Failed to add {sku}: {e}")
        return Response(status=500)
@app.post("/items/<sku>")
def check_item(sku: str):
    try:
        pricer.price_item({
            "sku": sku,
            "name": pricelist.to_name(sku)
        })
        price = pricelist.get_price(sku)
        if not price == None:
            logger.info(f"Checked price for {price["name"]}/{price["sku"]}.")
            return price
        return Response(status=404) # Return a 404 if we failed to functionally price the item
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

