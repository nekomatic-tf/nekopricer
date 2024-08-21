# Token Handler

import logging
from src.storage import S3Engine
from json import loads, dumps
from secrets import token_hex

class Tokens:
    logger = logging.getLogger("Token Manager")

    tokens = dict({"tokens": []})

    def __init__(self, s3engine: S3Engine):
        self.s3engine = s3engine

        # Who needs try-catch, if we can't write tokens.json then something is fucked up anyways
        self.logger.debug("Ignore error below, usually means tokens.json wasn't created before now.")
        self.read_tokens()
        self.write_tokens()
        self.read_tokens()
    def read_tokens(self):
        try:
            self.tokens = loads(self.s3engine.read_file("tokens.json"))
            self.logger.info("Read tokens.json")
        except Exception as e:
            self.logger.error(f"Failed to read tokens.json: {str(e)}")
    def write_tokens(self):
        try:
            self.s3engine.write_file("tokens.json", dumps(self.tokens))
            self.logger.info("Wrote tokens.json")
        except Exception as e:
            self.logger.error(f"Failed to write tokens.json: {str(e)}")
    
    def add_token(self):
        token = {
            "key": token_hex(25),
            "locked": False,
            #"expiration": "", <- work in progress tbh
            "user": ""
        }
        self.tokens["tokens"].append(token)
        self.logger.info(f"Created new token {token["key"]}")
        self.write_tokens()
        return token
    def delete_token(self, key: str):
        for token in self.tokens["tokens"]:
            if token["key"] == key:
                self.tokens["tokens"].remove(token)
                self.logger.info(f"Removed token {token["key"]}.")
                self.write_tokens()
                return True
        self.logger.error(f"Failed to find token {key}.")
        return False
    def lock_token(self, key: str, user: str):
        for token in self.tokens["tokens"]:
            if token["key"] == key:
                if token["locked"] == False:
                    token["locked"] = True
                    token["user"] = user
                    self.logger.info(f"Locked token {token["key"]} to user {token["user"]}.")
                    self.write_tokens()
                    return True
                else:
                    self.logger.warn(f"Token {token["key"]} is already locked to a user.")
                    return False
        self.logger.error(f"Failed to find token {key}.")
        return False
    def unlock_token(self, key: str):
        for token in self.tokens["tokens"]:
            if token["key"] == key:
                if token["locked"] == True:
                    token["locked"] = False
                    self.logger.info(f"Unlocked token {token["key"]}.")
                    self.write_tokens()
                    return True
                else:
                    self.logger.warn(f"Token {token["key"]} is not currently locked.")
                    return False
        self.logger.error(f"Failed to find token {key}.")
        return False
    def get_token(self, key: str):
        for token in self.tokens["tokens"]:
            if token["key"] == key:
                self.logger.info(f"Got token {token["key"]}.")
                return token
        self.logger.error(f"Failed to find token {key}.")
        return {"key": None}