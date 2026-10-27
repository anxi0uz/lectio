import asyncio
from datetime import timedelta
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import structlog
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from lectio.core.config import get_settings

log = structlog.get_logger(
    component="core.object_store",
)

MISSING_CODES = frozenset({"NoSuchKey", "NoSuchObject", "NoSuchBucket"})


def _client(
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
) -> Minio:
    url = urlsplit(endpoint)

    return Minio(
        url.netloc,
        access_key=access_key,
        secret_key=secret_key,
        secure=url.scheme == "https",
        region=region,
    )


class ObjectStore:
    """Files in an S3-compatible bucket, keyed like paths in the storage dir.

    The SDK is blocking, so every network call runs in a thread.
    """

    def __init__(
        self,
        endpoint: str,
        public_endpoint: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        url_ttl_seconds: int,
    ) -> None:
        self._client = _client(endpoint, access_key, secret_key, region)
        # A signature covers the host, so links for browsers are signed by a
        # client pointed at the address they use. Signing makes no requests.
        self._public = _client(
            public_endpoint or endpoint,
            access_key,
            secret_key,
            region,
        )
        self._bucket = bucket
        self._url_ttl = timedelta(seconds=url_ttl_seconds)

    async def ensure_bucket(self) -> None:
        if not await asyncio.to_thread(self._client.bucket_exists, self._bucket):
            await asyncio.to_thread(self._client.make_bucket, self._bucket)
            log.info("bucket_created", bucket=self._bucket)

    async def size(self, key: str) -> int | None:
        try:
            stat = await asyncio.to_thread(
                self._client.stat_object,
                self._bucket,
                key,
            )
        except S3Error as error:
            if error.code in MISSING_CODES:
                return None
            raise

        return stat.size

    async def upload(
        self,
        path: Path,
        key: str,
        content_type: str,
    ) -> None:
        size = (await anyio.Path(path).stat()).st_size

        # Reprocessing pulls the video down and would push the same bytes back.
        if await self.size(key) == size:
            return

        await asyncio.to_thread(
            self._client.fput_object,
            self._bucket,
            key,
            str(path),
            content_type=content_type,
        )

        log.info("object_uploaded", key=key, size_bytes=size)

    async def download(
        self,
        key: str,
        path: Path,
    ) -> bool:
        try:
            await asyncio.to_thread(
                self._client.fget_object,
                self._bucket,
                key,
                str(path),
            )
        except S3Error as error:
            if error.code in MISSING_CODES:
                return False
            raise

        log.info("object_downloaded", key=key)

        return True

    async def delete_prefix(self, prefix: str) -> None:
        def delete() -> None:
            objects = self._client.list_objects(
                self._bucket,
                prefix=prefix,
                recursive=True,
            )
            errors = self._client.remove_objects(
                self._bucket,
                (
                    DeleteObject(item.object_name)
                    for item in objects
                    if item.object_name
                ),
            )

            # Deletion is lazy: nothing happens until the errors are read.
            for error in errors:
                log.warning("object_delete_failed", error=str(error))

        await asyncio.to_thread(delete)

    def signed_url(self, key: str) -> str:
        return self._public.presigned_get_object(
            self._bucket,
            key,
            expires=self._url_ttl,
        )


@cache
def get_object_store() -> ObjectStore | None:
    """The bucket, or None when files stay on the local disk."""
    settings = get_settings()

    if settings.storage_backend != "s3":
        return None

    return ObjectStore(
        endpoint=settings.s3_endpoint,
        public_endpoint=settings.s3_public_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        url_ttl_seconds=settings.s3_url_ttl_seconds,
    )
