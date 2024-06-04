# Pricer API Server

import logging
from flask import Flask

class PricerAPIServer:
    logger = logging.getLogger(__name__)
    app = Flask(__name__)
    def __init__(self, config: dict):
        self.app.run(
            host=config["host"],
            port=config["port"]
        )
        self.logger.debug("Started API server.")