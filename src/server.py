# Pricer API Server

import logging
from flask import Flask
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)
app = Flask(__name__)
socket_io = SocketIO(app)
def start(config: dict):
    logger.debug("Starting API server...")
    app.run(
        host=config["host"],
        port=config["port"]
    )