from __future__ import annotations

from typing import Any

import boto3


def table_resource(table_name: str) -> Any:
    if not table_name:
        raise RuntimeError("TABLE_NAME is not configured")
    return boto3.resource("dynamodb").Table(table_name)


def s3_client() -> Any:
    return boto3.client("s3")
