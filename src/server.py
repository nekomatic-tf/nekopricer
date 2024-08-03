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
    try:
        price = pricelist.get_price(sku)
        name = pricelist.to_name(sku) # Get the name, or fail with server error 500 and log error
        if not price == None:
            pricer.price_item({ # Complete pricecheck
                "sku": price["sku"],
                "name": name
            })
            pricelist.add_item(name) # Enforce the whitelist
            price = pricelist.get_price(sku)
            logger.info(f"Refreshed price for {price["name"]}/{price["sku"]}.")
            return price # Return freshly priced item
        # Item isn't priced, attempt to price it
        pricer.price_item({
            "sku": sku,
            "name": name
        })
        price = pricelist.get_price(sku)
        if not price == None: # Item is functionally priced, whitelist it and return the price
            pricelist.add_item(name)
            logger.info(f"Refreshed price for {price["name"]}/{price["sku"]}.")
            return price
        logger.error(f"Failed to find a price for {name}/{sku}.")
        return Response(status=404) # Failed to functionally price the item, so return an error 404
    except Exception as e:
        logger.error(f"Failed to add {sku}: {e}") # Server error (duh)
        return Response(status=500)

@app.get("/health")
def get_health():
    custom_prices = sum(1 for item in pricelist.pricelist["items"] if item["source"] == "nekopricer")
    fallback_prices = sum(1 for item in pricelist.pricelist["items"] if item["source"] != "nekopricer")
    return {
        "item_list": {
            "total": len(pricelist.item_list["items"])
        },
        "pricelist": {
            "total": len(pricelist.pricelist["items"]),
            "custom": custom_prices,
            "fallback": fallback_prices
        },
        "pricer": pricer.statistics
    }

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

