from flask import Flask, Response
from flask_socketio import SocketIO
from src.pricelist import Pricelist
from src.pricer import Pricer
import logging

app = Flask(__name__)
socket = SocketIO(app)
logger = logging.getLogger("API Server")

# Socket
@socket.on("connect")
def on_connect(socket):
    logger.info(f"A new client connected to the socket: {socket}. (Should they be authenticated?)")
    pricelist.get_key_price() # Should we also emit all prices?
@socket.on("disconnect")
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

def init(
        host: str,
        port: int,
        _pricelist: Pricelist,
        _pricer: Pricer
):
    logger.info("Initializing API server...")
    global pricelist
    global pricer
    pricelist = _pricelist
    pricer = _pricer
    app.run(
        host,
        port
    )

