# Pricer API Server

import logging
from flask import Flask

logger = logging.getLogger(__name__)
app = Flask(__name__)

def start(config: dict):
    logger.debug("Starting API server...")
    app.run(
        host=config["host"],
        port=config["port"]
    )