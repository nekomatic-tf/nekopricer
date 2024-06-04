# Nekomatic.TF autopricer
print("Be gay, do crime.")

import logging
import sys
from asyncio import run
from json import load

async def main():
    logging.basicConfig(
        handlers=[
            logging.FileHandler('pricer.log'),
            logging.StreamHandler(sys.stdout)
        ],
        format="%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
        level=logging.DEBUG
    )
    logger = logging.getLogger(__name__)
    logger.debug("Logger started.")

    with open("config.json", "r") as f:
        config = load(f)

if __name__ == "__main__":
    run(main())