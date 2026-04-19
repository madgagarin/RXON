# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
from typing import Any

import pytest

from rxon.blob import BlobProvider, calculate_config_hash, parse_uri
from rxon.models import FileMetadata


def test_calculate_config_hash() -> None:
    h1 = calculate_config_hash("http://s3.local", "key123", "my-bucket")
    h2 = calculate_config_hash("http://s3.local", "key123", "my-bucket")
    assert h1 is not None
    assert h1 == h2
    assert len(h1) == 16

    assert calculate_config_hash(None, "key", "bucket") is None
    assert calculate_config_hash("http", "", "bucket") is None


def test_parse_uri_full() -> None:
    bucket, key, is_dir = parse_uri("s3://models/vision/yolo.pt")
    assert bucket == "models"
    assert key == "vision/yolo.pt"
    assert not is_dir


def test_parse_uri_directory() -> None:
    bucket, key, is_dir = parse_uri("s3://datasets/training/")
    assert bucket == "datasets"
    assert key == "training/"
    assert is_dir


def test_parse_uri_relative() -> None:
    bucket, key, is_dir = parse_uri("logs/today.txt", default_bucket="my-logs", prefix="worker-1/")
    assert bucket == "my-logs"
    assert key == "worker-1/logs/today.txt"


def test_parse_uri_negative() -> None:
    with pytest.raises(ValueError, match="without a default bucket"):
        parse_uri("some/path")

    with pytest.raises(ValueError):
        parse_uri("http://wrong-scheme.com/file")


def test_parse_uri_empty() -> None:
    with pytest.raises(ValueError):
        parse_uri("", default_bucket=None)


class MockBlobProvider(BlobProvider):
    async def upload(self, local_path: str, uri: str) -> FileMetadata:
        return FileMetadata(uri=uri, size=100, etag="fake-etag")

    async def download(self, uri: str, local_path: str) -> bool:
        return True

    async def get_metadata(self, uri: str) -> dict[str, Any] | None:
        return {}

    async def delete(self, uri: str) -> bool:
        return True

    async def delete_dir(self, uri: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_blob_provider_interface() -> None:
    # This is mainly to ensure the ABC can be subclassed with new methods
    provider = MockBlobProvider()
    assert await provider.delete("s3://b/f") is True
    assert await provider.delete_dir("s3://b/d/") is True
