# Nekopricer V3
print("Be gay, do crime.")

from logging import basicConfig, getLogger, DEBUG

basicConfig(level=DEBUG)
logger = getLogger(__name__)
logger.debug("Environment hasn't initialized (yet)")

from dotenv import load_dotenv

load_dotenv()

from .classes.options import Options

options = Options(None)

from logging import FileHandler, Formatter
from colorlog import StreamHandler, ColoredFormatter

logging_console_handler = StreamHandler()
logging_console_handler.setFormatter(ColoredFormatter("[ %(asctime)s ] [ %(log_color)s%(levelname)s%(reset)s ] [ %(name)s ]: %(message)s"))
logging_file_handler = FileHandler("app.log")
logging_file_handler.setFormatter(Formatter("[ %(asctime)s ] [ %(levelname)s ] [ %(name)s ]: %(message)s"))
basicConfig(
    handlers=[logging_console_handler, logging_file_handler],
    level=options.loggingLevel,
    force=True,
)
logger.debug("Logger initialized.")
logger.info("Welcome to Nekopricer V3")

from .library.minio import MinIO

minio = MinIO(
    endpoint=options.minioEndpoint,
    access_key=options.minioAccessKey,
    secret_key=options.minioSecretKey,
    bucket_name=options.minioBucketName,
    secure=options.minioSecure,
)

logger.debug("MinIO Initialized, loading Pricer...")

from .classes.pricer import Pricer

pricer = Pricer(minio)
pricer.start()
