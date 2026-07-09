from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import Asset


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"username": "demo", "password": "assetvault", "display_name": "Demo"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo", "password": "assetvault"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_and_stats_overview(client: TestClient) -> None:
    headers = register_and_login(client)
    response = client.get("/api/v1/stats/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_assets"] == 0
    assert data["type_stats"] == []


def test_project_can_reference_asset(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            name="stage.glb",
            stem="stage",
            extension="glb",
            asset_type="model",
            path="E:/assets/stage.glb",
            size_bytes=1024,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
    finally:
        db.close()

    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "演唱会项目", "description": "用于 MMD 舞台演示"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=headers,
        json={"asset_id": asset_id, "role": "stage"},
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["asset_count"] == 1
    assert detail["assets"][0]["role"] == "stage"
    assert detail["assets"][0]["asset"]["name"] == "stage.glb"


def test_settings_can_be_updated(client: TestClient) -> None:
    headers = register_and_login(client)

    response = client.get("/api/v1/settings", headers=headers)
    assert response.status_code == 200
    assert response.json()["theme"] == "system"
    assert response.json()["ai_api_key_configured"] is False

    response = client.patch(
        "/api/v1/settings",
        headers=headers,
        json={
            "theme": "dark",
            "cache_dir": "E:/AssetVault/cache",
            "ai_api_key": "sk-test",
            "ai_chat_model": "gpt-4o-mini",
            "thumbnail_quality": 90,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "dark"
    assert data["cache_dir"] == "E:/AssetVault/cache"
    assert data["ai_api_key_configured"] is True
    assert data["thumbnail_quality"] == 90

    response = client.post("/api/v1/settings/test-ai", headers=headers)
    assert response.status_code == 200
    assert response.json()["configured"] is True
