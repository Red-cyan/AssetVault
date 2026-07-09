from collections.abc import Generator
from pathlib import Path

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



def test_database_backup_rejects_memory_database(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)

    class FakeSettings:
        database_url = "sqlite:///:memory:"

    monkeypatch.setattr("backend.app.services.backup_service.get_settings", lambda: FakeSettings())
    response = client.post("/api/v1/settings/backup-database", headers=headers)
    assert response.status_code == 400
    assert "内存数据库无法备份" in response.json()["detail"]


def test_ai_analysis_generates_tags_and_description(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            name="concert_stage.glb",
            stem="concert_stage",
            extension="glb",
            asset_type="model",
            path="E:/assets/stage/concert_stage.glb",
            size_bytes=2048,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
    finally:
        db.close()

    response = client.post(f"/api/v1/ai/assets/{asset_id}/analyze", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "local-heuristic"
    assert "舞台" in data["tags"]
    assert data["asset"]["description"]
    assert any(tag["name"] == "舞台" for tag in data["asset"]["tags"])


def test_natural_language_search_returns_semantic_matches(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            name="concert_stage.glb",
            stem="concert_stage",
            extension="glb",
            asset_type="model",
            path="E:/assets/stage/concert_stage.glb",
            description="适合大型演唱会的舞台模型，包含 LED 背景。",
            size_bytes=2048,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
    finally:
        db.close()

    response = client.post(
        "/api/v1/search/natural-language",
        headers=headers,
        json={"query": "找一个适合演唱会的大舞台", "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"][0]["name"] == "concert_stage.glb"
    assert "舞台" in data["interpreted_keywords"]


def test_duplicate_detection_groups_same_content_files(
    client: TestClient,
    tmp_path: Path,
) -> None:
    headers = register_and_login(client)
    first = tmp_path / "stage-a.glb"
    second = tmp_path / "stage-b.glb"
    first.write_bytes(b"same model content")
    second.write_bytes(b"same model content")

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        db.add_all(
            [
                Asset(
                    user_id=user_id,
                    name="stage-a.glb",
                    stem="stage-a",
                    extension="glb",
                    asset_type="model",
                    path=str(first),
                    size_bytes=first.stat().st_size,
                ),
                Asset(
                    user_id=user_id,
                    name="stage-b.glb",
                    stem="stage-b",
                    extension="glb",
                    asset_type="model",
                    path=str(second),
                    size_bytes=second.stat().st_size,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/assets/duplicates", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_groups"] == 1
    assert data["total_assets"] == 2
    assert {item["name"] for item in data["groups"][0]["items"]} == {
        "stage-a.glb",
        "stage-b.glb",
    }


def test_asset_trash_lifecycle(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            name="unused_stage.glb",
            stem="unused_stage",
            extension="glb",
            asset_type="model",
            path="E:/assets/unused_stage.glb",
            size_bytes=1024,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
    finally:
        db.close()

    response = client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1

    response = client.get("/api/v1/assets", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = client.get("/api/v1/trash/assets", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["is_deleted"] is True

    response = client.post(f"/api/v1/trash/assets/{asset_id}/restore", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_deleted"] is False

    client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    response = client.delete(f"/api/v1/trash/assets/{asset_id}", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/v1/trash/assets", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
