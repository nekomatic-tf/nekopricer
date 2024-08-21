from flask import Flask, Response, request, Request
from flask_socketio import SocketIO, emit, disconnect
from src.pricelist import Pricelist
from src.pricer import Pricer
from src.storage import S3Engine
from..backpacktf import BackpackTF
import logging
from asyncio import new_event_loop
from src.server.tokens import Tokens

event_loop = new_event_loop()
app = Flask(__name__)
socket = SocketIO(app)
logger = logging.getLogger("API Server")

clients = list() # Maintain an in memory list of all authorized clients

def is_authorized(request: Request, socket: dict): # Determinate whether or not a client is authorized to access the API.
    if "127.0.0.1" in request.remote_addr:
        return True # Localhost, just authorize
    elif "Authorization" in request.headers:
        token = request.headers["Authorization"].removeprefix("Token ")
        if token == config["masterKey"]:
            return True # Master Key Authentication
        else:
            token = tokens.get_token(token)
            if token["key"] == None:
                return False # Token doesn't exist
            elif token["locked"] == True and request.remote_addr == token["user"]:
                return True # Everything looks good here.
            elif token["locked"] == True and not request.remote_addr == token["user"]:
                return False # User mismatch with token
            else:
                tokens.lock_token(token["key"], request.remote_addr)
                return True # Lock the token and authorize
    elif socket: # SocketIO auth
        if socket["token"] == config["masterKey"]:
            return True # Master Key Authentication
        else:
            token = tokens.get_token(socket["token"])
            if token["key"] == None:
                return False # Token doesn't exist
            elif token["locked"] == True and request.remote_addr == token["user"]:
                return True # Everything looks good here.
            elif token["locked"] == True and not request.remote_addr == token["user"]:
                return False # User mismatch with token
            else:
                tokens.lock_token(token["key"], request.remote_addr)
                return True # Lock the token auth authorize
    elif "key" in request.args and request.args["key"] == config["masterKey"]:
        return True # Me level access
    else:
        return False # You done fucked up :3

def is_operator(request: Request): # Determine whether or not the client is an operator
    if "127.0.0.1" in request.remote_addr or "key" in request.args and request.args["key"] == config["masterKey"]:
        return True
    else:
        return False

# Socket
@socket.on("connect")
def on_connect(socket):
    if is_authorized(request, socket):
        clients.append({request.sid, socket["token"]}) # Store an SID with its token
        emit("authenticated")
        logger.info(f"Authenticated new websocket client: {request.remote_addr}.")
        pricelist.emit_price(pricelist.key_price)
    else:
        emit("disconnect")
        disconnect()
@socket.on("disconnect")
def on_disconnect():
    logger.info(f"A client disconnected, we didn't even get to say goodbye :(")
# Routes
@app.get("/items")
def get_items():
    if is_authorized(request, None):
        logger.info(f"Got pricelist.")
        return pricelist.pricelist
    else:
        return Response(status=403)
@app.get("/items/<sku>")
@app.post("/items/<sku>")
def get_item(sku: str):
    if is_authorized(request, None):
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
    else:
        return Response(status=403)

@app.get("/health")
def get_health():
    if is_operator(request):
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
    else:
        return Response(status=403)

# Token Internal Endpoints
@app.get("/tokens") # Get all active tokens
def get_tokens():
    if is_operator(request):
        return tokens.tokens
    else:
        return Response(status=403)
@app.post("/tokens") # Add a token
def add_token():
    if is_operator(request):
        return tokens.add_token()
    else:
        return Response(status=403)
@app.get("/tokens/<key>")
def get_token(key: str):
    if is_operator(request):
        return tokens.get_token(key)
    else:
        return Response(status=403)
@app.delete("/tokens/<key>")
def delete_token(key: str):
    if is_operator(request):
        is_deleted = tokens.delete_token(key)
        if is_deleted:
            for sid, token in clients:
                if token == key:
                    disconnect(sid, namespace="/")
                    clients.remove(sid)
            return Response(status=200)
        else:
            return Response(status=404)
    else:
        return Response(status=403)

def init(
        _config: dict,
        _pricelist: Pricelist,
        _pricer: Pricer,
        _backpacktf: BackpackTF,
        _s3engine: S3Engine
):
    logger.info("Initializing API server...")
    global pricelist
    global pricer
    global backpacktf
    global s3engine
    global config
    pricelist = _pricelist
    pricer = _pricer
    backpacktf = _backpacktf
    s3engine = _s3engine
    config = _config

    global tokens
    tokens = Tokens(s3engine)

    app.run(
        _config["host"],
        _config["port"]
    )
