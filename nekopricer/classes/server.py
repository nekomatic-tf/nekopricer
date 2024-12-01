from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from flask import Flask, Request, request, Response
from flask_socketio import SocketIO


class Server:
    logger = getLogger("API Server")

    websocket_clients: dict = {}

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.app = Flask("API Server")
        self.socket = SocketIO(self.app)

        self.register_routes()

    def start(self):
        self.logger.info("Starting API Server...")
        self.app.run(host=self.pricer.options.host, port=self.pricer.options.port)

    def register_routes(self):
        self.app.get("/")(self.index)
        self.app.get("/items")(self.get_items)
        self.app.get("/items/<sku>")(self.get_item)
        self.app.post("/items/<sku>")(self.get_item)
        self.app.get("/health")(self.get_health)
        self.app.get("/tokens")(self.get_tokens)
        self.app.post("/tokens")(self.add_token)
        self.app.get("/tokens/<key>")(self.get_token)
        self.app.delete("/tokens/<key>")(self.delete_token)
        self.app.get("/options")(self.get_options)
        self.app.post("/options")(self.set_options)
        self.socket.on("connect")(self.on_connect)
        self.socket.on("disconnect")(self.on_disconnect)
        self.logger.debug("Registered all endpoints.")

    # Routes
    def index(self):
        return "Nekopricer V3"

    def get_items(self):
        if not self.api_authorize_user(request):
            return Response(status=403)
        return {"items": self.pricer.pricelist.pricelist}

    def get_item(self, sku: str):
        if not self.api_authorize_user(request):
            return Response(status=403)
        item = {"sku": sku}
        try:
            price = self.pricer.pricelist.get_price(item)
            item["name"] = self.pricer.pricelist.to_name(item["sku"])
            if price is not None:  # Item is priced, refresh price
                self.pricer.price_item(item)  # Perform a price check
                self.pricer.pricelist.add_item(item["name"])  # Ensure this item is in the item list
                price = self.pricer.pricelist.get_price(item)
                self.logger.info(f"Got price for {item["name"]}/{item["sku"]}")
                return price
            # Item isn't priced, attempt to price it
            self.pricer.price_item(item)
            price = self.pricer.pricelist.get_price(item)
            if price is not None:  # Functionally priced, not whitelisted yet
                self.pricer.pricelist.add_item(item["name"])  # Add item to the whitelist
                self.logger.info(f"Got price for {item["name"]}/{item["sku"]}")
                return price
            self.logger.error(f"Failed to get a price for {item["name"]}/{item["sku"]}")
            return Response(status=404)
        except Exception as e:
            self.logger.error(f"Failed to get a price for {item["sku"]}: {e}")
            return Response(status=500)

    def get_health(self):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        return {
            "item_list": {"total": len(self.pricer.pricelist.item_list)},
            "pricelist": self.pricer.pricelist.get_statistics(),
            "pricer": self.pricer.statistics,
        }

    def get_tokens(self):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        return {"tokens": self.pricer.tokens.tokens}

    def add_token(self):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        return self.pricer.tokens.add_token()

    def get_token(self, key: str):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        return self.pricer.tokens.get_token(key) or Response(status=404)

    def delete_token(self, key: str):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        if self.pricer.tokens.delete_token(key):
            if request.sid in self.websocket_clients:
                self.websocket_clients.pop(request.sid)
            return Response(status=200)
        return Response(status=404)

    def get_options(self):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        return self.pricer.options.jsonOptions

    def set_options(self):
        if not self.api_authorize_operator(request):
            return Response(status=403)
        data = request.get_json()
        self.pricer.options.jsonOptions = data
        self.pricer.options.saveOptions()
        return Response(status=200)

    # Sockets
    def on_connect(self, socket):
        if not self.socket_authorize_user(request, socket):
            self.socket.emit("blocked", {"expire": 60}, room=request.sid)
        else:
            self.websocket_clients[request.sid] = socket["token"]
            self.socket.emit("authenticated", room=request.sid)
            if self.pricer.options.jsonOptions["enforceKeyFallback"]:
                self.pricer.pricelist.emit_price(self.pricer.pricelist.key_price)

    def on_disconnect(self):
        self.websocket_clients.pop(request.sid)
        self.logger.info("A websocket client disconnected.")
        self.logger.debug("We never got to say goodbye...")

    # Authorizations
    def api_authorize_user(self, request: Request):
        if "127.0.0.1" in request.remote_addr:
            self.logger.info("Authorized localhost.")
            return True  # Localhost
        if "Authorization" in request.headers:
            token_key = request.headers["Authorization"].removeprefix("Token ")
            if token_key == self.pricer.options.masterKey:
                self.logger.info(f"Authorized client {request.remote_addr} using the master API key.")
                return True  # Master key
            return self.pricer.tokens.authorize_token(token_key, request.remote_addr, False)  # Let token manager decide
        if "key" in request.args and request.args["key"] == self.pricer.options.masterKey:
            self.logger.info(f"(WEB) Authorized client {request.remote_addr} using the master API key.")
            return True  # Master key using ?key= argument
        self.logger.warning(f"Failed to authorize client {request.remote_addr}.")
        return False

    def socket_authorize_user(self, request: Request, socket: dict):
        if "127.0.0.1" in request.remote_addr:
            self.logger.info("Authorized localhost.")
            return True  # Localhost
        if "token" in socket:
            if socket["token"] == self.pricer.options.masterKey:
                self.logger.info(f"Authorized websocket client {request.remote_addr} using the master API key.")
                return True  # Master key
            return self.pricer.tokens.authorize_token(socket["token"], request.remote_addr, False)  # Let token manager decide
        self.logger.warning(f"Failed to authorize websocket client {request.remote_addr}.")
        return False

    def api_authorize_operator(self, request: Request):
        if "127.0.0.1" in request.remote_addr:
            self.logger.info("Authorized localhost.")
            return True  # Localhost
        if "key" in request.args and request.args["key"] == self.pricer.options.masterKey:
            self.logger.info(f"Authorized client {request.remote_addr} using the master API key.")
            return True  # Master key

    def emit_to_clients(self, event: str, data: any):
        # Only emits to validates clients, clients that aren't "registered" get the silent treatment
        for websocket_client in self.websocket_clients:
            self.logger.debug(f"Emitted event '{event}' to authorized client {websocket_client}.")
            self.socket.emit(event, data, room=websocket_client)
