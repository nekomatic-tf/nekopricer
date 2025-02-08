from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger

class Pricelist:
    logger = getLogger("Pricelist")

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer
        return