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
@app.post("/items/<sku>")
def get_item(sku: str):
    price = pricelist.get_price(sku)
    if not price == None: # Item exists, but price it just to keep it up to date
        pricer.price_item({
            "sku": price["sku"],
            "name": price["name"]
        })
        price = pricelist.get_price(sku)
        return price
    try: # Item doesn't exist, attempt to price, then add or fail
        pricer.price_item({
            "sku": sku,
            "name": pricelist.to_name(sku)
        })
        price = pricelist.get_price(sku)
        if not price == None: # Item validated as priced, go ahead and add it to the item list
            pricelist.add_item(price["name"])
            return price 
        return Response(status=404) # Functionally failed to price
    except Exception as e:
        logger.error(f"Failed to add {sku}: {e}") # Server error (duh)
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

