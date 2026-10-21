import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["MDM_DATABASE_URL"] = "sqlite://"
os.environ["MDM_PUBLISH_LOCAL_DIR"] = str(ROOT / "pipelines" / ".local" / "publish")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.app import db as dbmod  # noqa: E402
from api.app.main import app  # noqa: E402
from api.seed import seed  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    import api.seed as seedmod

    seedmod.engine = engine
    seedmod.SessionLocal = dbmod.SessionLocal
    seed()
    with TestClient(app) as c:
        yield c
