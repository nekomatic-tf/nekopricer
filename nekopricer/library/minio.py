# MinIO Storage Engine

from logging import getLogger
from io import BytesIO
from minio import Minio


class MinIO:
    logger = getLogger("MinIO Storage Engine")

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool,
    ):
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket_name = bucket_name

        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            self.logger.debug(f"Created new bucket {self.bucket_name}.")
        self.logger.debug("Initialized MinIO.")

    def file_exists(self, file: str) -> bool:
        try:
            self.client.stat_object(bucket_name=self.bucket_name, object_name=file)
            return True
        except Exception:
            return False

    def read_file(self, file: str):
        content = self.client.get_object(bucket_name=self.bucket_name, object_name=file)
        self.logger.debug(f"Read {file}.")
        return content.data.decode(encoding="utf-8")

    def write_file(self, file: str, content: str):
        data = BytesIO(content.encode(encoding="utf-8"))
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=file,
            data=data,
            length=len(content),
        )
        self.logger.debug(f"Wrote {file}.")
