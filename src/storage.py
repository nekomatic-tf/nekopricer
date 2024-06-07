# MinIO engine

import logging
import io
from minio import Minio

class MinIOEngine:
    logger = logging.getLogger(__name__)

    def __init__(self, config: dict):
        self.bucket = config["bucket"]
        self.client = Minio(
            endpoint=config["endpoint"],
            access_key=config["key"],
            secret_key=config["secret"],
            secure=config["secure"]
        )

        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            self.logger.debug("Created bucket " + self.bucket)
    
    def write_file(self, file: str, content: str):
        data = io.BytesIO(content.encode(encoding="utf-8"))
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=file,
            data=data,
            length=len(content)
        )
        self.logger.debug("Wrote " + file)

    def read_file(self, file: str):
        try:
            content = self.client.get_object(
                bucket_name=self.bucket,
                object_name=file
            )
            self.logger.debug("Read " + file)
            return content.data.decode(encoding="utf-8")
        except Exception as e:
            self.logger.error("Error reading " + file + ": " + str(e))
            return e
