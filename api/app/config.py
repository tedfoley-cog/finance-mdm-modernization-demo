"""Runtime configuration. Everything comes from the environment (RDS URL, S3 bucket, warehouse mode)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    publish_bucket: str
    publish_prefix: str
    environment: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ.get("MDM_DATABASE_URL", "sqlite:///./ledgercore.db"),
            publish_bucket=os.environ.get("MDM_PUBLISH_BUCKET", "ledgercore-mdm-publish-dev"),
            publish_prefix=os.environ.get("MDM_PUBLISH_PREFIX", "golden"),
            environment=os.environ.get("MDM_ENV", "dev"),
        )


settings = Settings.from_env()
