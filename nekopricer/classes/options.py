from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from typing import TypedDict
from json import loads, dumps
from os import getenv
from jsonschema import validate
from ..schemas.options import options_schema


class MaxPercentageDifferences(TypedDict):
    buy: int
    sell: int


class Intervals(TypedDict):
    snapshot: int
    price: int
    pricelist: int
    key: int


class PricingOptions(TypedDict):
    onlyBots: bool
    allowCutting: bool
    allowSnipping: bool
    allowMatching: bool
    allowRounding: bool
    allowBacking: bool
    buyLimit: int
    sellLimit: int
    buyLimitStrict: bool
    sellLimitStrict: bool
    buyHumanFallback: bool
    sellHumanFallback: bool
    partialBuyFallback: bool
    partialSellFallback: bool


class BlockedAttributes(TypedDict):
    name: str
    defindex: int


class JsonOptions(TypedDict):
    maxPercentageDifferences: MaxPercentageDifferences
    intervals: Intervals
    pricingOptions: PricingOptions
    enforceKeyFallback: bool
    excludedSteamIDs: list[str]
    trustedSteamIDs: list[str]
    excludedListingDescriptions: list[str]
    blockedAttributes: list[BlockedAttributes]
    paints: list[str]


DEFAULTS: JsonOptions = {
    "maxPercentageDifferences": {"buy": 5, "sell": -8},
    "intervals": {"snapshot": 60, "price": 60, "pricelist": 60, "key": 60},
    "pricingOptions": {
        "onlyBots": True,
        "allowCutting": False,
        "allowSnipping": False,
        "allowMatching": False,
        "allowRounding": True,
        "allowBacking": False,
        "buyLimit": 5,
        "sellLimit": 5,
        "buyLimitStrict": True,
        "sellLimitStrict": True,
        "buyHumanFallback": False,
        "sellHumanFallback": False,
        "partialBuyFallback": False,
        "partialSellFallback": False,
    },
    "enforceKeyFallback": True,
    "excludedSteamIDs": [
        "76561199384015307",
        "76561199495073910",
        "76561199222202498",
        "76561199501640256",
        "76561199501799493",
        "76561199465040669",
        "76561199468045911",
        "76561198871163068",
        "76561198274855163",
        "76561199523234411",
        "76561199500884711",
        "76561199518117301",
        "76561199181551276",
        "76561198266870398",
        "76561199402715445",
        "76561198094818081",
        "76561198068640262",
        "76561198380634252",
        "76561199543568974",
        "76561199542850733",
        "76561199545913929",
        "76561199545638184",
        "76561199545797558",
        "76561199545847539",
        "76561198170365551",
        "76561199530079519",
        "76561199530617017",
        "76561199522203126",
    ],
    "trustedSteamIDs": [
        "76561199110778355",
        "76561199057187154",
        "76561198225717852",
        "76561199118546232",
        "76561198316831771",
        "76561198428177474",
        "76561199072654974",
        "76561198453530349",
        "76561198259733876",
    ],
    "excludedListingDescriptions": [
        "exorcism",
        "ex",
        "spell",
        "spells",
        "spelled",
        "footsteps",
        "hh",
        "horseshoes/rotten orange",
        "headless horse",
        "pumpkin bombs",
    ],
    "blockedAttributes": [
        {"name": "Painted Items", "defindex": 142},
        {"name": "SPELL: set item tint RGB", "defindex": 1004},
        {"name": "SPELL: set Halloween footstep type", "defindex": 1005},
        {"name": "SPELL: Halloween voice modulation", "defindex": 1006},
        {"name": "SPELL: Halloween pumpkin explosions", "defindex": 1007},
        {"name": "SPELL: Halloween green flames", "defindex": 1008},
        {"name": "SPELL: Halloween death ghosts", "defindex": 1009},
        {"name": "Strange Part", "defindex": 379},
        {"name": "Strange Part", "defindex": 380},
        {"name": "Strange Part", "defindex": 381},
        {"name": "Strange Part", "defindex": 382},
        {"name": "Strange Part", "defindex": 383},
        {"name": "Strange Part", "defindex": 384},
    ],
    "paints": [
        "A Color Similar to Slate",
        "Indubitably Green",
        "A Deep Commitment to Purple",
        "Mann Co. Orange",
        "A Distinctive Lack of Hue",
        "Muskelmannbraun",
        "A Mann's Mint",
        "Noble Hatter's Violet",
        "After Eight",
        "Peculiarly Drab Tincture",
        "Aged Moustache Grey",
        "Pink as Hell",
        "An Extraordinary Abundance of Tinge",
        "Radigan Conagher Brown",
        "Australium Gold",
        "The Bitter Taste of Defeat and Lime",
        "Color No. 216-190-216",
        "The Color of a Gentlemann's Business Pants",
        "Dark Salmon Injustice",
        "Ye Olde Rustic Colour",
        "Drably Olive",
        "Zepheniah's Greed",
        "An Air of Debonair",
        "Team Spirit",
        "Balaclavas Are Forever",
        "The Value of Teamwork",
        "Cream Spirit",
        "Waterlogged Lab Coat",
        "Operator's Overalls",
        "Non-Craftable A Color Similar to Slate",
        "Non-Craftable Indubitably Green",
        "Non-Craftable A Deep Commitment to Purple",
        "Non-Craftable Mann Co. Orange",
        "Non-Craftable A Distinctive Lack of Hue",
        "Non-Craftable Muskelmannbraun",
        "Non-Craftable A Mann's Mint",
        "Non-Craftable Noble Hatter's Violet",
        "Non-Craftable After Eight",
        "Non-Craftable Peculiarly Drab Tincture",
        "Non-Craftable Aged Moustache Grey",
        "Non-Craftable Pink as Hell",
        "Non-Craftable An Extraordinary Abundance of Tinge",
        "Non-Craftable Radigan Conagher Brown",
        "Non-Craftable Australium Gold",
        "Non-Craftable The Bitter Taste of Defeat and Lime",
        "Non-Craftable Color No. 216-190-216",
        "Non-Craftable The Color of a Gentlemann's Business Pants",
        "Non-Craftable Dark Salmon Injustice",
        "Non-Craftable Ye Olde Rustic Colour",
        "Non-Craftable Drably Olive",
        "Non-Craftable Zepheniah's Greed",
        "Non-Craftable An Air of Debonair",
        "Non-Craftable Team Spirit",
        "Non-Craftable Balaclavas Are Forever",
        "Non-Craftable The Value of Teamwork",
        "Non-Craftable Cream Spirit",
        "Non-Craftable Waterlogged Lab Coat",
        "Non-Craftable Operator's Overalls",
    ],
}


class Options:
    # Environment variable based options
    loggingLevel: str

    masterKey: str

    backpackTfApiKey: str
    backpackTfAccessToken: str
    backpackTfSnapshotUrl: str
    backpackTfWebsocketUrl: str

    pricesTfApiUrl: str
    pricesTfWebsocketUrl: str

    autobotTfUrl: str
    autobotTfSchemaUrl: str

    steamApiKey: str

    mongoUri: str
    mongoDb: str
    mongoCollection: str

    minioEndpoint: str
    minioAccessKey: str
    minioSecretKey: str
    minioBucketName: str
    minioSecure: bool

    host: str
    port: int

    # JSON options
    jsonOptions: JsonOptions

    logger = getLogger("Options")

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

        self.loggingLevel = getOption("LOGGING_LEVEL", "INFO", str)

        self.masterKey = getOption("MASTER_KEY", None, str)

        self.backpackTfApiKey = getOption("BACKPACK_TF_API_KEY", "", str)
        self.backpackTfAccessToken = getOption("BACKPACK_TF_ACCESS_TOKEN", None, str)
        self.backpackTfSnapshotUrl = getOption("BACKPACK_TF_SNAPSHOT_URL", "https://backpack.tf/api/classifieds/listings/snapshot", str)
        self.backpackTfWebsocketUrl = getOption("BACKPACK_TF_WEBSOCKET_URL", "wss://ws.backpack.tf/events", str)

        self.pricesTfApiUrl = getOption("PRICES_TF_API_URL", "https://api2.prices.tf", str)
        self.pricesTfWebsocketUrl = getOption("PRICES_TF_WEBSOCKET_URL", "wss://ws.prices.tf", str)

        self.autobotTfUrl = getOption("AUTOBOT_TF_URL", "https://autobot.tf", str)
        self.autobotTfSchemaUrl = getOption("AUTOBOT_TF_SCHEMA_URL", "https://schema.autobot.tf", str)

        self.steamApiKey = getOption("STEAM_API_KEY", "", str)

        self.mongoUri = getOption("MONGO_URI", None, str)
        self.mongoDb = getOption("MONGO_DB", "backpacktf", str)
        self.mongoCollection = getOption("MONGO_COLLECTION", "listings", str)

        self.minioEndpoint = getOption("MINIO_ENDPOINT", None, str)
        self.minioAccessKey = getOption("MINIO_ACCESS_KEY", None, str)
        self.minioSecretKey = getOption("MINIO_SECRET_KEY", None, str)
        self.minioBucketName = getOption("MINIO_BUCKET_NAME", "nekopricer", str)
        self.minioSecure = getOption("MINIO_SECURE", False, loads)

        self.host = getOption("HOST", "localhost", str)
        self.port = getOption("PORT", 3456, int)

        self.jsonOptions = DEFAULTS

    def loadOptions(self):
        try:
            if not self.pricer.minio.file_exists("options.json"):
                self.pricer.minio.write_file("options.json", dumps(self.jsonOptions))
                self.logger.debug("Created options.json")
            jsonOptions = loads(self.pricer.minio.read_file("options.json"))
            validate(jsonOptions, options_schema)
            self.jsonOptions.update(jsonOptions)
            self.logger.info("Loaded options.")
        except Exception as e:
            self.logger.error(f"Failed to load options: {e}")

    def saveOptions(self):
        try:
            validate(self.jsonOptions, options_schema)
            self.pricer.minio.write_file("options.json", dumps(self.jsonOptions))
            self.logger.info("Saved options.")
        except Exception as e:
            self.logger.error(f"Failed saving options: {e}")


def getOption(option: str, default: any, parseFn: callable) -> any:
    optionValue = getenv(option)
    if optionValue is None and default is None:
        raise Exception(f"Missing required environment variable: {option}")
    elif optionValue is None and default is not None:
        return default
    else:
        try:
            optionValue = parseFn(optionValue)
        except Exception as e:
            raise Exception(f"Failed to parse environment variable {option}: {e}")
        return optionValue
