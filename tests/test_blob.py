# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
import pytest

from rxon.blob import calculate_config_hash, parse_uri


def test_calculate_config_hash():
    # Positive
    h1 = calculate_config_hash("http://s3.local", "key123", "my-bucket")
    h2 = calculate_config_hash("http://s3.local", "key123", "my-bucket")
    assert h1 == h2
    assert len(h1) == 16

    # Negative: missing fields
    assert calculate_config_hash(None, "key", "bucket") is None
    assert calculate_config_hash("http", "", "bucket") is None


def test_parse_uri_full():
    bucket, key, is_dir = parse_uri("s3://models/vision/yolo.pt")
    assert bucket == "models"
    assert key == "vision/yolo.pt"
    assert not is_dir


def test_parse_uri_directory():
    bucket, key, is_dir = parse_uri("s3://datasets/training/")
    assert bucket == "datasets"
    assert key == "training/"
    assert is_dir


def test_parse_uri_relative():
    # With default bucket and prefix
    bucket, key, is_dir = parse_uri("logs/today.txt", default_bucket="my-logs", prefix="worker-1/")
    assert bucket == "my-logs"
    assert key == "worker-1/logs/today.txt"


def test_parse_uri_negative():
    # 1. Relative path without default bucket
    with pytest.raises(ValueError, match="without a default bucket"):
        parse_uri("some/path")

    # 2. Malformed or different scheme (should be treated as relative if not s3://)
    # But if no default bucket is provided, it fails.
    with pytest.raises(ValueError):
        parse_uri("http://wrong-scheme.com/file")


def test_parse_uri_empty():
    with pytest.raises(ValueError):
        parse_uri("", default_bucket=None)
