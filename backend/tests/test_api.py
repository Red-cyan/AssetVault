import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import hash_password
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import Asset, AssetTag, Folder, Tag, Task, User
from backend.app.services.ai_analysis_service import AiAnalysisError, AnalysisResult
from backend.app.services.asset_scanner import scan_folder
from backend.app.services.embedding_service import index_user_assets
from backend.app.services.file_type_service import get_asset_type

TEST_DATABASE_URL = os.getenv(
    "ASSETVAULT_TEST_DATABASE_URL",
    "postgresql+psycopg://assetvault:assetvault@127.0.0.1:5432/assetvault_test",
)


def set_auth_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr("backend.app.api.deps.get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.api.v1.auth.get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.api.v1.runtime.get_settings", lambda: settings)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    set_auth_settings(monkeypatch, get_settings().model_copy(update={"auth_mode": "password"}))
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
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
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def local_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, Settings]]:
    settings = get_settings().model_copy(update={"auth_mode": "local", "local_user_id": None})
    set_auth_settings(monkeypatch, settings)
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, settings
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


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


def test_runtime_reports_password_mode(client: TestClient) -> None:
    response = client.get("/api/v1/runtime")
    assert response.status_code == 200
    assert response.json() == {
        "auth_mode": "password",
        "authentication_required": True,
    }


def test_local_mode_creates_workspace_and_disables_password_auth(
    local_client: tuple[TestClient, Settings],
) -> None:
    client, _ = local_client
    assert client.get("/api/v1/runtime").json() == {
        "auth_mode": "local",
        "authentication_required": False,
    }

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "local"
    assert client.get("/api/v1/stats/overview").status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "local", "password": "irrelevant"},
    )
    register = client.post(
        "/api/v1/auth/register",
        json={"username": "another", "password": "assetvault"},
    )
    assert login.status_code == 403
    assert register.status_code == 403


def test_local_mode_reuses_only_existing_user(
    local_client: tuple[TestClient, Settings],
) -> None:
    client, _ = local_client
    db = next(app.dependency_overrides[get_db]())
    try:
        user = User(
            username="demo",
            display_name="Demo",
            password_hash=hash_password("assetvault"),
        )
        db.add(user)
        db.commit()
        expected_id = user.id
    finally:
        db.close()

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["id"] == expected_id
    assert response.json()["username"] == "demo"


def test_local_mode_requires_selection_for_multiple_users(
    local_client: tuple[TestClient, Settings],
) -> None:
    client, settings = local_client
    db = next(app.dependency_overrides[get_db]())
    try:
        first = User(username="first", password_hash=hash_password("first-password"))
        second = User(username="second", password_hash=hash_password("second-password"))
        db.add_all([first, second])
        db.commit()
        selected_id = second.id
    finally:
        db.close()

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 503
    assert "ASSETVAULT_LOCAL_USER_ID" in response.json()["detail"]

    settings.local_user_id = selected_id
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["id"] == selected_id


def test_auth_and_stats_overview(client: TestClient) -> None:
    headers = register_and_login(client)
    response = client.get("/api/v1/stats/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_assets"] == 0
    assert data["type_stats"] == []


def test_multiple_users_can_register_without_email(client: TestClient) -> None:
    first = client.post(
        "/api/v1/auth/register",
        json={"username": "demo-a", "password": "assetvault"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/register",
        json={"username": "demo-b", "password": "assetvault"},
    )
    assert second.status_code == 201


def test_user_profile_and_password_can_be_updated(client: TestClient) -> None:
    headers = register_and_login(client)

    response = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"display_name": "AssetVault Demo", "email": "demo@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "AssetVault Demo"
    assert data["email"] == "demo@example.com"

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "other",
            "password": "assetvault",
            "email": "other@example.com",
        },
    )
    response = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"email": "other@example.com"},
    )
    assert response.status_code == 409

    response = client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-assetvault"},
    )
    assert response.status_code == 400

    response = client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "assetvault", "new_password": "new-assetvault"},
    )
    assert response.status_code == 204

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo", "password": "assetvault"},
    )
    assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo", "password": "new-assetvault"},
    )
    assert response.status_code == 200


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


def test_project_can_be_updated(client: TestClient) -> None:
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Old Name", "description": "Old description"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "New Name", "description": "New description"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["description"] == "New description"

    response = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["description"] == "New description"


def test_project_manifest_can_be_exported_as_json_and_csv(client: TestClient) -> None:
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
            file_hash="hash-stage",
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
        json={"name": "Concert Demo", "description": "Stage manifest demo"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/assets",
        headers=headers,
        json={"asset_id": asset_id, "role": "stage"},
    )
    assert response.status_code == 200

    response = client.get(f"/api/v1/projects/{project_id}/export", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["project"]["name"] == "Concert Demo"
    assert data["project"]["asset_count"] == 1
    assert data["assets"][0]["name"] == "concert_stage.glb"
    assert data["assets"][0]["role"] == "stage"
    assert data["assets"][0]["file_hash"] == "hash-stage"

    response = client.get(
        f"/api/v1/projects/{project_id}/export?format=csv",
        headers=headers,
    )
    assert response.status_code == 200
    assert "project_name,role,asset_name" in response.text
    assert "Concert Demo,stage,concert_stage.glb" in response.text

    response = client.get(
        f"/api/v1/projects/{project_id}/export?format=xlsx",
        headers=headers,
    )
    assert response.status_code == 400


def test_project_can_add_assets_in_batch(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        assets = [
            Asset(
                user_id=user_id,
                name="character.pmx",
                stem="character",
                extension="pmx",
                asset_type="model",
                path="E:/assets/character.pmx",
                size_bytes=1024,
            ),
            Asset(
                user_id=user_id,
                name="dance.vmd",
                stem="dance",
                extension="vmd",
                asset_type="motion",
                path="E:/assets/dance.vmd",
                size_bytes=2048,
            ),
        ]
        db.add_all(assets)
        db.commit()
        asset_ids = []
        for asset in assets:
            db.refresh(asset)
            asset_ids.append(asset.id)
    finally:
        db.close()

    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Batch Demo"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/assets/batch",
        headers=headers,
        json={"asset_ids": asset_ids, "role": "character"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["asset_count"] == 2
    assert {item["asset"]["name"] for item in data["assets"]} == {"character.pmx", "dance.vmd"}
    assert {item["role"] for item in data["assets"]} == {"character"}

    response = client.post(
        f"/api/v1/projects/{project_id}/assets/batch",
        headers=headers,
        json={"asset_ids": asset_ids, "role": "motion"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["asset_count"] == 2
    assert {item["role"] for item in data["assets"]} == {"motion"}


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



def test_database_backup_rejects_non_postgres_database(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)

    class FakeSettings:
        database_url = "sqlite:///:memory:"

    monkeypatch.setattr("backend.app.services.backup_service.get_settings", lambda: FakeSettings())
    response = client.post("/api/v1/settings/backup-database", headers=headers)
    assert response.status_code == 400
    assert "仅支持 PostgreSQL" in response.json()["detail"]


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
    assert data["asset"]["description"] is None
    assert data["asset"]["tags"] == []

    response = client.post(
        f"/api/v1/ai/assets/{asset_id}/apply",
        headers=headers,
        json={
            "tags": data["tags"],
            "description": data["description"],
            "source": data["source"],
        },
    )
    assert response.status_code == 200
    assert response.json()["asset"]["description"]
    assert any(tag["name"] == "舞台" for tag in response.json()["asset"]["tags"])


def test_ai_analysis_uses_openai_compatible_when_configured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            name="anime_blue_hair.png",
            stem="anime_blue_hair",
            extension="png",
            asset_type="image",
            path="E:/assets/characters/anime_blue_hair.png",
            size_bytes=2048,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
    finally:
        db.close()

    response = client.patch(
        "/api/v1/settings",
        headers=headers,
        json={"ai_api_key": "sk-test", "ai_base_url": "https://example.com/v1"},
    )
    assert response.status_code == 200

    def fake_call_openai_compatible(settings: dict, asset: Asset) -> AnalysisResult:
        assert settings["ai_api_key"] == "sk-test"
        assert asset.name == "anime_blue_hair.png"
        return AnalysisResult(
            tags=["人物", "蓝发", "动漫"],
            description="这是一个蓝发动漫人物参考图。",
            source="openai-compatible",
        )

    monkeypatch.setattr(
        "backend.app.services.ai_analysis_service.call_openai_compatible",
        fake_call_openai_compatible,
    )

    response = client.post(f"/api/v1/ai/assets/{asset_id}/analyze", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "openai-compatible"
    assert data["description"] == "这是一个蓝发动漫人物参考图。"
    assert data["tags"] == ["人物", "蓝发", "动漫"]
    assert data["asset"]["tags"] == []


def test_ai_analysis_does_not_fall_back_when_configured_model_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    client.patch(
        "/api/v1/settings",
        headers=headers,
        json={"ai_api_key": "sk-test"},
    )

    def fail_ai_call(settings: dict, asset: Asset) -> AnalysisResult:
        raise AiAnalysisError("AI request failed: rate limited")

    monkeypatch.setattr(
        "backend.app.services.ai_analysis_service.call_openai_compatible",
        fail_ai_call,
    )
    response = client.post(f"/api/v1/ai/assets/{asset_id}/analyze", headers=headers)
    assert response.status_code == 502
    assert "rate limited" in response.json()["detail"]

    response = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.json()["description"] is None
    assert response.json()["tags"] == []


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


def test_pgvector_index_hybrid_search_and_similar_assets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)

    def fake_encode(texts: list[str]) -> list[list[float]]:
        result = []
        for value in texts:
            vector = [0.0] * 1024
            if "舞台" in value or "演出空间" in value:
                vector[0] = 1.0
            else:
                vector[1] = 1.0
            result.append(vector)
        return result

    monkeypatch.setattr("backend.app.services.embedding_service.encode_texts", fake_encode)
    monkeypatch.setattr("backend.app.services.search_service.encode_texts", fake_encode)

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        stage = Asset(
            user_id=user_id,
            name="main.glb",
            stem="main",
            extension="glb",
            asset_type="model",
            path="E:/assets/main.glb",
            description="大型未来舞台，带有 LED 屏幕",
            size_bytes=2048,
        )
        character = Asset(
            user_id=user_id,
            name="hero.pmx",
            stem="hero",
            extension="pmx",
            asset_type="model",
            path="E:/assets/hero.pmx",
            description="动漫人物角色",
            size_bytes=1024,
        )
        task = Task(user_id=user_id, type="embedding", status="pending")
        db.add_all([stage, character, task])
        db.commit()
        db.refresh(stage)
        db.refresh(character)
        db.refresh(task)

        index_user_assets(db, task_id=task.id, user_id=user_id)
        db.refresh(task)
        assert task.status == "success"
        assert task.result["indexed"] == 2
        stage_id = stage.id

        second_task = Task(user_id=user_id, type="embedding", status="pending")
        db.add(second_task)
        db.commit()
        db.refresh(second_task)
        index_user_assets(db, task_id=second_task.id, user_id=user_id)
        db.refresh(second_task)
        assert second_task.result["indexed"] == 0
        assert second_task.result["skipped"] == 2
    finally:
        db.close()

    response = client.post(
        "/api/v1/search/natural-language",
        headers=headers,
        json={"query": "未来演出空间", "limit": 10},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid-bge-m3"
    assert response.json()["items"][0]["id"] == stage_id

    response = client.get("/api/v1/search/embeddings/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["indexed_assets"] == 2
    assert response.json()["dimensions"] == 1024

    response = client.get(f"/api/v1/search/similar/{stage_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


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


def test_assets_can_be_updated_in_batch(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        assets = [
            Asset(
                user_id=user_id,
                name="stage-a.glb",
                stem="stage-a",
                extension="glb",
                asset_type="model",
                path="E:/assets/stage-a.glb",
                size_bytes=1024,
            ),
            Asset(
                user_id=user_id,
                name="stage-b.glb",
                stem="stage-b",
                extension="glb",
                asset_type="model",
                path="E:/assets/stage-b.glb",
                size_bytes=2048,
            ),
        ]
        db.add_all(assets)
        db.commit()
        asset_ids = []
        for asset in assets:
            db.refresh(asset)
            asset_ids.append(asset.id)
    finally:
        db.close()

    response = client.patch(
        "/api/v1/assets/batch",
        headers=headers,
        json={
            "asset_ids": asset_ids,
            "is_favorite": True,
            "tag_names": ["舞台", "演唱会"],
        },
    )
    assert response.status_code == 200
    assert response.json()["matched_count"] == 2
    assert response.json()["updated_count"] == 2
    assert response.json()["tagged_count"] == 4

    db = next(app.dependency_overrides[get_db]())
    try:
        stored_assets = list(db.scalars(select(Asset).where(Asset.id.in_(asset_ids))))
        assert all(asset.is_favorite for asset in stored_assets)
        tags = list(db.scalars(select(Tag).where(Tag.name.in_(["舞台", "演唱会"]))))
        assert {tag.name for tag in tags} == {"舞台", "演唱会"}
        link_count = db.query(AssetTag).filter(AssetTag.asset_id.in_(asset_ids)).count()
        assert link_count == 4
    finally:
        db.close()

    response = client.patch(
        "/api/v1/assets/batch",
        headers=headers,
        json={"asset_ids": asset_ids, "move_to_trash": True},
    )
    assert response.status_code == 200
    assert response.json()["trashed_count"] == 2

    response = client.get("/api/v1/assets", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_asset_list_defaults_to_primary_scope(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        db.add_all(
            [
                Asset(
                    user_id=user_id,
                    name="character.pmx",
                    stem="character",
                    extension="pmx",
                    asset_type="model",
                    path="E:/assets/character/character.pmx",
                    size_bytes=1024,
                ),
                Asset(
                    user_id=user_id,
                    name="dance.vmd",
                    stem="dance",
                    extension="vmd",
                    asset_type="motion",
                    path="E:/assets/motion/dance.vmd",
                    size_bytes=512,
                ),
                Asset(
                    user_id=user_id,
                    name="body_diffuse.png",
                    stem="body_diffuse",
                    extension="png",
                    asset_type="image",
                    path="E:/assets/character/textures/body_diffuse.png",
                    size_bytes=2048,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/assets", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert {item["name"] for item in data["items"]} == {"character.pmx", "dance.vmd"}

    response = client.get("/api/v1/assets?scope=support", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "body_diffuse.png"

    response = client.get("/api/v1/assets?scope=all", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 3

    response = client.get("/api/v1/assets?scope=primary&type=image", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_assets_can_be_grouped_and_filtered_by_project_folder(client: TestClient) -> None:
    headers = register_and_login(client)
    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        folder = Folder(user_id=user_id, name="MMD Library", path="E:/assets")
        db.add(folder)
        db.commit()
        db.refresh(folder)
        db.add_all(
            [
                Asset(
                    user_id=user_id,
                    folder_id=folder.id,
                    name="miku.pmx",
                    stem="miku",
                    extension="pmx",
                    asset_type="model",
                    path="E:/assets/miku/miku.pmx",
                    size_bytes=1000,
                ),
                Asset(
                    user_id=user_id,
                    folder_id=folder.id,
                    name="body.png",
                    stem="body",
                    extension="png",
                    asset_type="image",
                    path="E:/assets/miku/textures/body.png",
                    size_bytes=2000,
                ),
                Asset(
                    user_id=user_id,
                    folder_id=folder.id,
                    name="stage.glb",
                    stem="stage",
                    extension="glb",
                    asset_type="model",
                    path="E:/assets/stage/stage.glb",
                    size_bytes=3000,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/assets/folder-groups", headers=headers)
    assert response.status_code == 200
    groups = response.json()
    miku_group = next(item for item in groups if item["name"] == "miku")
    assert miku_group["total_count"] == 2
    assert miku_group["primary_count"] == 1
    assert miku_group["support_count"] == 1

    response = client.get(
        "/api/v1/assets?scope=all&directory_path=E:/assets/miku",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert {item["name"] for item in data["items"]} == {"miku.pmx", "body.png"}

    response = client.get(
        "/api/v1/assets?directory_path=E:/assets/miku",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "miku.pmx"


def test_tags_can_be_updated_and_deleted(client: TestClient) -> None:
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
        f"/api/v1/assets/{asset_id}/tags",
        headers=headers,
        json={"tag_names": ["舞台"]},
    )
    assert response.status_code == 200
    tag_id = response.json()["tags"][0]["id"]

    response = client.patch(
        f"/api/v1/tags/{tag_id}",
        headers=headers,
        json={"name": "演出舞台", "color": "#2563eb"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "演出舞台"
    assert response.json()["color"] == "#2563eb"

    response = client.post(
        "/api/v1/tags",
        headers=headers,
        json={"name": "灯光"},
    )
    assert response.status_code == 201
    conflict_tag_id = response.json()["id"]

    response = client.patch(
        f"/api/v1/tags/{conflict_tag_id}",
        headers=headers,
        json={"name": "演出舞台"},
    )
    assert response.status_code == 409

    response = client.delete(f"/api/v1/tags/{tag_id}", headers=headers)
    assert response.status_code == 204

    response = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "stage.glb"
    assert all(tag["name"] != "演出舞台" for tag in response.json()["tags"])


def test_folder_scan_marks_missing_and_restores_assets(
    client: TestClient,
    tmp_path: Path,
) -> None:
    headers = register_and_login(client)
    first_file = tmp_path / "stage-a.glb"
    second_file = tmp_path / "stage-b.glb"
    first_file.write_bytes(b"stage-a")
    second_file.write_bytes(b"stage-b")

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        folder = Folder(user_id=user_id, name="demo", path=str(tmp_path))
        task = Task(user_id=user_id, type="scan", status="pending")
        db.add_all([folder, task])
        db.commit()
        db.refresh(folder)
        db.refresh(task)

        scan_folder(db, task_id=task.id, user_id=user_id, folder_id=folder.id)
        db.refresh(task)
        assert task.result["imported"] == 2

        second_file.unlink()
        existing_asset = db.scalar(select(Asset).where(Asset.path == str(first_file.resolve())))
        assert existing_asset is not None
        existing_asset.exists_on_disk = False
        db.commit()

        rescan_task = Task(user_id=user_id, type="scan", status="pending")
        db.add(rescan_task)
        db.commit()
        db.refresh(rescan_task)

        scan_folder(db, task_id=rescan_task.id, user_id=user_id, folder_id=folder.id)
        db.refresh(rescan_task)

        restored_asset = db.scalar(select(Asset).where(Asset.path == str(first_file.resolve())))
        missing_asset = db.scalar(select(Asset).where(Asset.path == str(second_file.resolve())))
        assert restored_asset is not None
        assert missing_asset is not None
        assert restored_asset.exists_on_disk is True
        assert restored_asset.missing_since is None
        assert missing_asset.exists_on_disk is False
        assert missing_asset.missing_since is not None
        assert rescan_task.result["restored"] == 1
        assert rescan_task.result["missing_marked"] == 1
    finally:
        db.close()


def test_folder_rescan_skips_hash_and_thumbnail_for_unchanged_file(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)
    source = tmp_path / "poster.png"
    source.write_bytes(b"not-a-real-image")
    calls = {"hash": 0, "thumbnail": 0}

    def fake_hash(_path: Path) -> str:
        calls["hash"] += 1
        return "fingerprint"

    def fake_thumbnail(_asset_id: str, _path: Path) -> str:
        calls["thumbnail"] += 1
        return str(tmp_path / "thumbnail.jpg")

    monkeypatch.setattr("backend.app.services.asset_scanner.calculate_file_fingerprint", fake_hash)
    monkeypatch.setattr(
        "backend.app.services.asset_scanner.generate_image_thumbnail", fake_thumbnail
    )

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        folder = Folder(user_id=user_id, name="demo", path=str(tmp_path))
        first_task = Task(user_id=user_id, type="scan", status="pending")
        db.add_all([folder, first_task])
        db.commit()
        db.refresh(folder)
        db.refresh(first_task)

        scan_folder(db, task_id=first_task.id, user_id=user_id, folder_id=folder.id)
        assert calls == {"hash": 1, "thumbnail": 1}

        second_task = Task(user_id=user_id, type="scan", status="pending")
        db.add(second_task)
        db.commit()
        db.refresh(second_task)
        scan_folder(db, task_id=second_task.id, user_id=user_id, folder_id=folder.id)
        db.refresh(second_task)

        assert calls == {"hash": 1, "thumbnail": 1}
        assert second_task.result["unchanged"] == 1
        assert second_task.result["updated"] == 0
    finally:
        db.close()


def test_folder_rescan_backfills_new_extractor_without_rehashing(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)
    source = tmp_path / "Concert.uproject"
    source.write_text(
        '{"FileVersion": 3, "EngineAssociation": "5.5", '
        '"Description": "演唱会工程"}',
        encoding="utf-8",
    )
    calls = {"hash": 0}

    def fake_hash(_path: Path) -> str:
        calls["hash"] += 1
        return "fingerprint"

    monkeypatch.setattr("backend.app.services.asset_scanner.calculate_file_fingerprint", fake_hash)

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        folder = Folder(user_id=user_id, name="demo", path=str(tmp_path))
        first_task = Task(user_id=user_id, type="scan", status="pending")
        db.add_all([folder, first_task])
        db.commit()
        scan_folder(db, task_id=first_task.id, user_id=user_id, folder_id=folder.id)

        asset = db.scalar(select(Asset).where(Asset.path == str(source.resolve())))
        assert asset is not None
        asset.extractor_name = "generic"
        asset.extraction_status = "metadata_only"
        asset.extracted_metadata = {}
        asset.extracted_text = None
        asset.semantic_eligible = False
        db.commit()

        second_task = Task(user_id=user_id, type="scan", status="pending")
        db.add(second_task)
        db.commit()
        scan_folder(db, task_id=second_task.id, user_id=user_id, folder_id=folder.id)
        db.refresh(asset)

        assert calls["hash"] == 1
        assert asset.extractor_name == "uproject-json"
        assert asset.extracted_metadata["engine_association"] == "5.5"
        assert asset.semantic_eligible is True
    finally:
        db.close()


def test_folder_scan_records_file_failure_and_continues(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = register_and_login(client)
    bad_file = tmp_path / "broken.glb"
    good_file = tmp_path / "stage.glb"
    bad_file.write_bytes(b"broken")
    good_file.write_bytes(b"stage")

    def sometimes_fails(path: Path) -> str:
        if path == bad_file:
            raise OSError("file became unavailable")
        return "fingerprint"

    monkeypatch.setattr(
        "backend.app.services.asset_scanner.calculate_file_fingerprint", sometimes_fails
    )

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        folder = Folder(user_id=user_id, name="demo", path=str(tmp_path))
        task = Task(user_id=user_id, type="scan", status="pending")
        db.add_all([folder, task])
        db.commit()
        db.refresh(folder)
        db.refresh(task)

        scan_folder(db, task_id=task.id, user_id=user_id, folder_id=folder.id)
        db.refresh(task)

        assert task.status == "success"
        assert task.result["imported"] == 1
        assert task.result["failed"] == 1
        assert task.result["failures"][0]["path"] == str(bad_file)
        assert task.result["failures"][0]["retry_count"] == 1
    finally:
        db.close()


def test_scan_task_conflict_cancel_and_retry(client: TestClient, tmp_path: Path) -> None:
    headers = register_and_login(client)
    source = tmp_path / "stage.glb"
    source.write_bytes(b"stage")
    response = client.post(
        "/api/v1/folders",
        headers=headers,
        json={"path": str(tmp_path), "name": "Demo Folder"},
    )
    folder_id = response.json()["id"]

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        running_task = Task(
            user_id=user_id,
            type="scan",
            status="running",
            payload={"folder_id": folder_id, "path": str(tmp_path)},
        )
        db.add(running_task)
        db.commit()
        db.refresh(running_task)
        task_id = running_task.id
    finally:
        db.close()

    response = client.post(f"/api/v1/folders/{folder_id}/scan", headers=headers)
    assert response.status_code == 409

    response = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"

    response = client.post(f"/api/v1/tasks/{task_id}/retry", headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["payload"]["retry_of"] == task_id


def test_delete_folder_keeps_asset_index(client: TestClient, tmp_path: Path) -> None:
    headers = register_and_login(client)
    source = tmp_path / "stage.glb"
    source.write_bytes(b"stage")

    response = client.post(
        "/api/v1/folders",
        headers=headers,
        json={"path": str(tmp_path), "name": "Demo Folder"},
    )
    assert response.status_code == 201
    folder_id = response.json()["id"]

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        asset = Asset(
            user_id=user_id,
            folder_id=folder_id,
            name="stage.glb",
            stem="stage",
            extension="glb",
            asset_type="model",
            path=str(source),
            size_bytes=source.stat().st_size,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
    finally:
        db.close()

    response = client.delete(f"/api/v1/folders/{folder_id}", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/v1/folders", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    response = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "stage.glb"

    db = next(app.dependency_overrides[get_db]())
    try:
        stored = db.get(Asset, asset_id)
        assert stored is not None
        assert stored.folder_id is None
    finally:
        db.close()


def test_missing_asset_scan_marks_and_restores_files(
    client: TestClient,
    tmp_path: Path,
) -> None:
    headers = register_and_login(client)
    existing = tmp_path / "exists.glb"
    missing = tmp_path / "missing.glb"
    existing.write_bytes(b"exists")

    db = next(app.dependency_overrides[get_db]())
    try:
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
        db.add_all(
            [
                Asset(
                    user_id=user_id,
                    name="exists.glb",
                    stem="exists",
                    extension="glb",
                    asset_type="model",
                    path=str(existing),
                    size_bytes=existing.stat().st_size,
                ),
                Asset(
                    user_id=user_id,
                    name="missing.glb",
                    stem="missing",
                    extension="glb",
                    asset_type="model",
                    path=str(missing),
                    size_bytes=8,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/assets/missing/scan", headers=headers)
    assert response.status_code == 200
    assert response.json()["checked_count"] == 2
    assert response.json()["missing_count"] == 1

    response = client.get("/api/v1/assets/missing", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "missing.glb"

    missing.write_bytes(b"restored")
    response = client.post("/api/v1/assets/missing/scan", headers=headers)
    assert response.status_code == 200
    assert response.json()["restored_count"] == 1

    response = client.get("/api/v1/assets/missing", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_hdr_and_exr_are_supported_image_assets() -> None:
    assert get_asset_type(Path("studio_light.hdr")) == "image"
    assert get_asset_type(Path("skybox.exr")) == "image"
