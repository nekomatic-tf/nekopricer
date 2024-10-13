from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pricer import Pricer

from logging import getLogger
from json import loads, dumps
from secrets import token_hex
from jsonschema import validate
from ..schemas.tokens import tokens_schema


class Tokens:
    logger = getLogger("Tokens")

    tokens: list = []

    def __init__(self, pricer: "Pricer"):
        self.pricer = pricer

    def read_tokens(self):
        try:
            if not self.pricer.minio.file_exists("tokens.json"):
                self.logger.debug("Attempting to create new tokens.json...")
                self.pricer.minio.write_file("tokens.json", dumps({"tokens": self.tokens}))
            tokens = loads(self.pricer.minio.read_file("tokens.json"))
            validate(tokens, tokens_schema)
            self.tokens = tokens["tokens"]
            self.logger.info("Read tokens.")
        except Exception as e:
            self.logger.error(f"Failed to read tokens: {e}")

    def write_tokens(self):
        try:
            validate({"tokens": self.tokens}, tokens_schema)
            self.pricer.minio.write_file("tokens.json", dumps({"tokens": self.tokens}))
            self.logger.info("Wrote tokens.")
        except Exception as e:
            self.logger.error(f"Failed to write tokens: {e}")

    def add_token(self) -> dict:
        token = {"key": token_hex(25), "locked": False, "user": ""}
        self.tokens.append(token)
        self.write_tokens()
        self.logger.info(f"Created new token {token["key"]}.")
        return token

    def get_token(self, key: str) -> dict:
        for token in self.tokens:
            if token["key"] == key:
                self.logger.info(f"Got token {key}.")
                return token
        self.logger.warning(f"Failed to find token {key}.")
        return None

    def delete_token(self, key: str) -> bool:
        for token in self.tokens:
            if token["key"] == key:
                self.tokens.remove(token)
                self.write_tokens()
                self.logger.info(f"Removed token {key}.")
                return True
        self.logger.warning(f"Failed to delete missing token {key}.")
        return False

    def lock_token(self, key: str, user: str) -> bool:
        for token in self.tokens:
            if token["key"] == key:
                if not token["locked"]:
                    token["locked"] = True
                    token["user"] = user
                    self.write_tokens()
                    self.logger.info(f"Locked token {key} to user {user}.")
                    return True
                else:
                    self.logger.warning(f"Token {key} is already locked to user {token["user"]}.")
                    return False
        self.logger.warning(f"Failed to lock missing token {key}.")
        return False

    def unlock_token(self, key: str) -> bool:
        for token in self.tokens:
            if token["key"] == key:
                if token["locked"]:
                    token["locked"] = False
                    token["user"] = ""
                    self.write_tokens()
                    self.logger.info(f"Unlocked token {key}.")
                    return True
                else:
                    self.logger.warning(f"Token {key} is not current locked to a user.")
                    return False
        self.logger.warning(f"Failed to unlock missing token {key}.")
        return False

    def authorize_token(self, key: str, user: str, lock: bool) -> bool:
        token = self.get_token(key)
        if token is not None:
            if token["locked"] and token["user"] == user:
                self.logger.info(f"Authorized token {key} owned by user {user}.")
                return True  # Locked, user matches
            if token["locked"] and not token["user"] == user:
                self.logger.warning(f"Token {key} belongs to a different {user}.")
                return False  # Locked, user mismatch
            if not token["locked"]:
                if lock:
                    self.logger.debug(f"Locked token {key} to user {user}.")
                    self.lock_token(key)
                self.logger.info(f"Authorized token {key}.")
                return True  # Unlocked, user doesn't matter
            return False  # Fallback
        else:
            return False
