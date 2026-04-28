"""
Tests for Materials API - Material library management.

Tests material library endpoints:
- POST /api/v1/materials/upload - Upload material
- GET /api/v1/materials - Get material list
- GET /api/v1/materials/library-summary - Get library summary
- GET /api/v1/materials/search - Search materials
- GET /api/v1/materials/{novel_id} - Get material detail
- DELETE /api/v1/materials/{novel_id} - Delete material
"""

import io
import json
import os
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select

import api.materials.upload as materials_upload_api
from api.materials.constants import MAX_TEXT_CHARACTERS
from core.error_codes import ErrorCode
from models import File, Project, User
from models.material_models import (
    Chapter,
    Character,
    CharacterRelationship,
    GoldenFinger,
    IngestionJob,
    Novel,
    Story,
    StoryLine,
    WorldView,
)
from models.subscription import SubscriptionPlan, UserSubscription

# ==================== Helper Functions ====================


@pytest.fixture(autouse=True)
def stub_flow_dispatch(monkeypatch):
    async def _fake_start_flow_deployment(*args, **kwargs):
        return "flow-run-test"

    monkeypatch.setattr(
        materials_upload_api,
        "_start_flow_deployment",
        _fake_start_flow_deployment,
    )


async def create_test_user(client: AsyncClient, db_session, username: str = "testuser") -> tuple[User, str]:
    """Create a test user and return (user, token)."""
    from services.core.auth_service import hash_password

    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    paid_plan = db_session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
    ).first()
    if paid_plan is None:
        paid_plan = SubscriptionPlan(
            name="pro",
            display_name="Pro",
            display_name_en="Pro",
            price_monthly_cents=4900,
            price_yearly_cents=39900,
            features={
                "materials_library_access": True,
                "material_uploads": 5,
                "material_decompositions": 5,
                "ai_conversations_per_day": -1,
                "max_projects": -1,
            },
            is_active=True,
        )
        db_session.add(paid_plan)
        db_session.commit()
        db_session.refresh(paid_plan)

    existing_subscription = db_session.exec(
        select(UserSubscription).where(UserSubscription.user_id == user.id)
    ).first()
    if existing_subscription is None:
        now = datetime.utcnow()
        db_session.add(
            UserSubscription(
                user_id=user.id,
                plan_id=paid_plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        db_session.commit()

    login_response = await client.post(
        "/api/auth/login", data={"username": username, "password": "password123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return user, token


def create_test_novel(db_session, user_id: str, title: str = "Test Novel") -> Novel:
    """Create a test novel."""
    novel = Novel(user_id=user_id, title=title, author="Test Author")
    db_session.add(novel)
    db_session.commit()
    return novel


def create_test_job(db_session, novel_id: int, status: str = "completed") -> IngestionJob:
    """Create a test ingestion job."""
    job = IngestionJob(
        novel_id=novel_id,
        source_path="/tmp/test.txt",
        status=status,
        total_chapters=10,
        processed_chapters=10,
    )
    db_session.add(job)
    db_session.commit()
    return job


# ==================== Upload Tests ====================


def test_decode_upload_text_falls_back_to_gb18030_when_detector_is_low_confidence():
    """GBK/GB18030 novels should decode correctly even when chardet guesses wrong."""
    content = "字" * 32

    decoded = materials_upload_api._decode_upload_text(content.encode("gbk"))

    assert decoded == content


def test_decode_upload_text_strips_utf16_bom_from_character_count():
    """UTF-16 BOM should not count as an extra character."""
    content = "字" * 32

    decoded = materials_upload_api._decode_upload_text(content.encode("utf-16"))

    assert decoded == content


@pytest.mark.integration
async def test_upload_material_success(client: AsyncClient, db_session):
    """Test successful material upload."""
    user, token = await create_test_user(client, db_session, "uploaduser1")

    # Create a test file
    file_content = b"Chapter 1\n\nThis is test content for the novel."
    file = ("test_novel.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        params={"title": "My Test Novel", "author": "Test Author"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My Test Novel"
    assert data["status"] == "pending"
    assert "novel_id" in data
    assert "job_id" in data


@pytest.mark.integration
async def test_upload_material_accepts_content_at_character_limit(
    client: AsyncClient,
    db_session,
    monkeypatch,
    tmp_path,
):
    """Materials upload should accept files up to the 300k-character cap."""
    from config.material_settings import material_settings

    _, token = await create_test_user(client, db_session, "uploaduser_limit_ok")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    file_content = ("字" * MAX_TEXT_CHARACTERS).encode("utf-8")
    file = ("limit_ok.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


@pytest.mark.integration
async def test_upload_material_accepts_gbk_content_at_character_limit(
    client: AsyncClient,
    db_session,
    monkeypatch,
    tmp_path,
):
    """GBK-encoded novels at the limit should not be rejected as oversized."""
    from config.material_settings import material_settings

    _, token = await create_test_user(client, db_session, "uploaduser_limit_ok_gbk")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    file_content = ("字" * MAX_TEXT_CHARACTERS).encode("gbk")
    file = ("limit_ok_gbk.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


@pytest.mark.integration
async def test_upload_material_accepts_utf16_content_at_character_limit(
    client: AsyncClient,
    db_session,
    monkeypatch,
    tmp_path,
):
    """UTF-16 BOM novels at the limit should not be rejected as oversized."""
    from config.material_settings import material_settings

    _, token = await create_test_user(client, db_session, "uploaduser_limit_ok_utf16")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    file_content = ("字" * MAX_TEXT_CHARACTERS).encode("utf-16")
    file = ("limit_ok_utf16.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


@pytest.mark.integration
async def test_upload_material_rejects_content_over_character_limit(
    client: AsyncClient,
    db_session,
    monkeypatch,
    tmp_path,
):
    """Materials upload should reject files over the 300k-character cap."""
    from config.material_settings import material_settings

    _, token = await create_test_user(client, db_session, "uploaduser_limit_too_long")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    file_content = ("字" * (MAX_TEXT_CHARACTERS + 1)).encode("utf-8")
    file = ("limit_too_long.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == ErrorCode.FILE_CONTENT_TOO_LONG
    assert payload["error_code"] == ErrorCode.FILE_CONTENT_TOO_LONG


@pytest.mark.integration
async def test_upload_material_returns_503_when_flow_dispatch_fails(client: AsyncClient, db_session, monkeypatch):
    """Upload should not claim success if flow dispatch fails."""
    _, token = await create_test_user(client, db_session, "upload_dispatch_fail")

    async def _failed_start_flow_deployment(*args, **kwargs):
        return None

    monkeypatch.setattr(
        materials_upload_api,
        "_start_flow_deployment",
        _failed_start_flow_deployment,
    )

    file_content = b"Chapter 1\n\nThis is test content for the novel."
    file = ("test_novel.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503


@pytest.mark.integration
async def test_upload_material_sanitizes_filename(client: AsyncClient, db_session, monkeypatch, tmp_path):
    """Upload should sanitize dangerous filename segments before writing to disk."""
    from config.material_settings import material_settings

    _, token = await create_test_user(client, db_session, "uploaduser_sanitize")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    file_content = b"Chapter 1\n\nSafe content"
    file = ("../unsafe/../../novel.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    novel_id = response.json()["novel_id"]
    novel = db_session.get(Novel, novel_id)
    assert novel is not None

    source_meta = json.loads(novel.source_meta or "{}")
    file_path = source_meta.get("file_path", "")
    assert file_path
    assert str(tmp_path) in file_path
    assert ".." not in os.path.basename(file_path)


@pytest.mark.integration
async def test_upload_material_invalid_extension(client: AsyncClient, db_session):
    """Test upload with invalid file extension returns 400."""
    user, token = await create_test_user(client, db_session, "uploaduser2")

    # Try to upload a .pdf file (not allowed)
    file_content = b"PDF content"
    file = ("test.pdf", io.BytesIO(file_content), "application/pdf")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.integration
async def test_upload_material_requires_paid_materials_access(client: AsyncClient, db_session):
    """Free users should receive a feature-not-included error when uploading."""
    from services.core.auth_service import hash_password

    user = User(
        username="freeuploaduser",
        email="freeuploaduser@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    file = ("test_novel.txt", io.BytesIO(b"hello"), "text/plain")
    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 402
    data = response.json()
    assert data["error_code"] == "ERR_FEATURE_NOT_INCLUDED"


@pytest.mark.integration
async def test_upload_material_without_auth(client: AsyncClient, db_session):
    """Test upload without authentication returns 401."""
    file_content = b"Test content"
    file = ("test.txt", io.BytesIO(file_content), "text/plain")

    response = await client.post(
        "/api/v1/materials/upload",
        files={"file": file},
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_internal_worker_download_success(client: AsyncClient, db_session, monkeypatch, tmp_path):
    """Worker internal endpoint should download file with valid internal token."""
    from config.material_settings import material_settings

    user, _ = await create_test_user(client, db_session, "workerdownload1")
    monkeypatch.setenv("MATERIAL_INTERNAL_TOKEN", "worker-token")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    filename = f"{user.id}_20260219_test.txt"
    file_path = tmp_path / filename
    file_path.write_text("worker file content", encoding="utf-8")

    response = await client.get(
        f"/api/v1/materials/internal/system/files/{filename}",
        params={"user_id": user.id},
        headers={"X-Internal-Token": "worker-token"},
    )

    assert response.status_code == 200
    assert response.text == "worker file content"


@pytest.mark.integration
async def test_internal_worker_download_invalid_token(client: AsyncClient, db_session, monkeypatch, tmp_path):
    """Worker internal endpoint should reject invalid token."""
    from config.material_settings import material_settings

    user, _ = await create_test_user(client, db_session, "workerdownload2")
    monkeypatch.setenv("MATERIAL_INTERNAL_TOKEN", "worker-token")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    filename = f"{user.id}_20260219_test.txt"
    file_path = tmp_path / filename
    file_path.write_text("worker file content", encoding="utf-8")

    response = await client.get(
        f"/api/v1/materials/internal/system/files/{filename}",
        params={"user_id": user.id},
        headers={"X-Internal-Token": "wrong-token"},
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_internal_worker_download_user_mismatch(client: AsyncClient, db_session, monkeypatch, tmp_path):
    """Worker internal endpoint should block cross-user file access."""
    from config.material_settings import material_settings

    owner, _ = await create_test_user(client, db_session, "workerdownload3")
    other_user, _ = await create_test_user(client, db_session, "workerdownload4")
    monkeypatch.setenv("MATERIAL_INTERNAL_TOKEN", "worker-token")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    filename = f"{owner.id}_20260219_test.txt"
    file_path = tmp_path / filename
    file_path.write_text("worker file content", encoding="utf-8")

    response = await client.get(
        f"/api/v1/materials/internal/system/files/{filename}",
        params={"user_id": other_user.id},
        headers={"X-Internal-Token": "worker-token"},
    )

    assert response.status_code == 403


# ==================== Get Materials List Tests ====================


@pytest.mark.integration
async def test_get_materials_empty(client: AsyncClient, db_session):
    """Test getting materials when user has none."""
    user, token = await create_test_user(client, db_session, "listuser1")

    response = await client.get(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.integration
async def test_get_materials_with_data(client: AsyncClient, db_session):
    """Test getting materials list with data."""
    user, token = await create_test_user(client, db_session, "listuser2")

    # Create novels with jobs
    novel1 = create_test_novel(db_session, user.id, "Novel 1")
    novel2 = create_test_novel(db_session, user.id, "Novel 2")
    novel1.source_meta = json.dumps({"original_filename": "novel1.txt"})
    create_test_job(db_session, novel1.id, "completed")
    processing_job = create_test_job(db_session, novel2.id, "processing")
    processing_job.error_message = "processing error"
    db_session.add(processing_job)
    db_session.commit()

    # Add chapters to novel1
    chapter = Chapter(novel_id=novel1.id, chapter_number=1, title="Chapter 1")
    db_session.add(chapter)
    db_session.commit()

    response = await client.get(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Check that chapters_count is included
    novel1_item = next((item for item in data if item["title"] == "Novel 1"), None)
    assert novel1_item is not None
    assert novel1_item["chapters_count"] == 1
    assert novel1_item["original_filename"] == "novel1.txt"
    novel2_item = next((item for item in data if item["title"] == "Novel 2"), None)
    assert novel2_item is not None
    assert novel2_item["error_message"] == "processing error"


@pytest.mark.integration
async def test_get_materials_excludes_deleted(client: AsyncClient, db_session):
    """Test that materials list excludes soft-deleted novels."""
    from datetime import datetime

    user, token = await create_test_user(client, db_session, "listuser3")

    novel1 = create_test_novel(db_session, user.id, "Active Novel")
    novel2 = create_test_novel(db_session, user.id, "Deleted Novel")
    novel2.deleted_at = datetime.utcnow()
    db_session.commit()

    create_test_job(db_session, novel1.id, "completed")
    create_test_job(db_session, novel2.id, "completed")

    response = await client.get(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Active Novel"


@pytest.mark.integration
async def test_get_materials_user_isolation(client: AsyncClient, db_session):
    """Test that users can only see their own materials."""
    user1, token1 = await create_test_user(client, db_session, "listuser4")
    user2, _ = await create_test_user(client, db_session, "listuser5")

    # Create novel for user2
    novel2 = create_test_novel(db_session, user2.id, "User2 Novel")
    create_test_job(db_session, novel2.id, "completed")

    # Get materials as user1
    response = await client.get(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0  # User1 should see nothing


# ==================== Library Summary Tests ====================


@pytest.mark.integration
async def test_get_library_summary_empty(client: AsyncClient, db_session):
    """Test library summary when user has no materials."""
    user, token = await create_test_user(client, db_session, "summaryuser1")

    response = await client.get(
        "/api/v1/materials/library-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.integration
async def test_get_library_summary_only_completed(client: AsyncClient, db_session):
    """Test that library summary only includes completed novels."""
    user, token = await create_test_user(client, db_session, "summaryuser2")

    # Create novels with different statuses
    novel_completed = create_test_novel(db_session, user.id, "Completed Novel")
    novel_processing = create_test_novel(db_session, user.id, "Processing Novel")
    novel_failed = create_test_novel(db_session, user.id, "Failed Novel")

    create_test_job(db_session, novel_completed.id, "completed")
    create_test_job(db_session, novel_processing.id, "processing")
    create_test_job(db_session, novel_failed.id, "failed")

    response = await client.get(
        "/api/v1/materials/library-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Completed Novel"


@pytest.mark.integration
async def test_get_library_summary_with_counts(client: AsyncClient, db_session):
    """Test library summary returns correct entity counts."""
    user, token = await create_test_user(client, db_session, "summaryuser3")

    novel = create_test_novel(db_session, user.id, "Novel With Entities")
    create_test_job(db_session, novel.id, "completed")

    # Add entities
    character1 = Character(novel_id=novel.id, name="Character 1")
    character2 = Character(novel_id=novel.id, name="Character 2")
    db_session.add_all([character1, character2])
    db_session.commit()  # Commit first to get character IDs

    worldview = WorldView(novel_id=novel.id, power_system="Test Power System")
    db_session.add(worldview)

    golden_finger = GoldenFinger(novel_id=novel.id, name="Golden Finger 1")
    db_session.add(golden_finger)

    storyline = StoryLine(novel_id=novel.id, title="Story Line 1")
    db_session.add(storyline)
    db_session.commit()
    db_session.refresh(storyline)

    db_session.add(
        Story(
            story_line_id=storyline.id,
            title="Story 1",
            synopsis="Story in summary counts",
        )
    )

    # Now create relationship with committed character IDs
    relationship = CharacterRelationship(
        novel_id=novel.id,
        character_a_id=character1.id,
        character_b_id=character2.id,
        relationship_type="friend",
    )
    db_session.add(relationship)
    db_session.commit()

    response = await client.get(
        "/api/v1/materials/library-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    counts = data[0]["counts"]
    assert counts["characters"] == 2
    assert counts["worldview"] == 1
    assert counts["golden_fingers"] == 1
    assert counts["stories"] == 1
    assert counts["storylines"] == 1
    assert counts["relationships"] == 1


@pytest.mark.integration
async def test_get_material_status_reconciles_stale_pending_job(client: AsyncClient, db_session):
    """Status endpoint should fail stale pending jobs instead of leaving them hanging forever."""
    user, token = await create_test_user(client, db_session, "statususer1")

    novel = create_test_novel(db_session, user.id, "Stale Pending Novel")
    job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="pending",
        total_chapters=10,
        processed_chapters=0,
    )
    stale_time = datetime.utcnow() - timedelta(hours=1)
    job.created_at = stale_time
    job.updated_at = stale_time
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = await client.get(
        f"/api/v1/materials/{novel.id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "拆解任务调度超时，请重试"


# ==================== Search Tests ====================


@pytest.mark.integration
async def test_search_materials_empty_query(client: AsyncClient, db_session):
    """Test search with no completed novels returns empty."""
    user, token = await create_test_user(client, db_session, "searchuser1")

    response = await client.get(
        "/api/v1/materials/search",
        params={"q": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.integration
async def test_search_materials_characters(client: AsyncClient, db_session):
    """Test searching for characters."""
    user, token = await create_test_user(client, db_session, "searchuser2")

    novel = create_test_novel(db_session, user.id, "Search Novel")
    create_test_job(db_session, novel.id, "completed")

    character = Character(
        novel_id=novel.id, name="Zhang San", description="A brave warrior"
    )
    db_session.add(character)
    db_session.commit()

    response = await client.get(
        "/api/v1/materials/search",
        params={"q": "Zhang"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(item["entity_type"] == "characters" for item in data)


@pytest.mark.integration
async def test_search_materials_only_completed(client: AsyncClient, db_session):
    """Test that search only includes completed novels."""
    user, token = await create_test_user(client, db_session, "searchuser3")

    novel_completed = create_test_novel(db_session, user.id, "Completed")
    novel_processing = create_test_novel(db_session, user.id, "Processing")

    create_test_job(db_session, novel_completed.id, "completed")
    create_test_job(db_session, novel_processing.id, "processing")

    # Add characters to both
    char1 = Character(novel_id=novel_completed.id, name="Hero")
    char2 = Character(novel_id=novel_processing.id, name="Villain")
    db_session.add_all([char1, char2])
    db_session.commit()

    response = await client.get(
        "/api/v1/materials/search",
        params={"q": "Hero"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # Should only find Hero from completed novel
    assert any(item["name"] == "Hero" for item in data)


# ==================== Material Detail Tests ====================


@pytest.mark.integration
async def test_get_material_detail_success(client: AsyncClient, db_session):
    """Test getting material detail successfully."""
    user, token = await create_test_user(client, db_session, "detailuser1")

    novel = create_test_novel(db_session, user.id, "Detail Novel")
    novel.synopsis = "A test synopsis"
    create_test_job(db_session, novel.id, "completed")

    # Add entities
    chapter = Chapter(novel_id=novel.id, chapter_number=1, title="Chapter 1")
    character = Character(novel_id=novel.id, name="Character 1")
    storyline = StoryLine(novel_id=novel.id, title="Story Line 1")
    golden_finger = GoldenFinger(novel_id=novel.id, name="GF 1")
    worldview = WorldView(novel_id=novel.id, power_system="Power")
    db_session.add_all([chapter, character, storyline, golden_finger, worldview])
    db_session.commit()

    response = await client.get(
        f"/api/v1/materials/{novel.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == novel.id
    assert data["title"] == "Detail Novel"
    assert data["synopsis"] == "A test synopsis"
    assert data["status"] == "completed"
    assert data["chapters_count"] == 1
    assert data["characters_count"] == 1
    assert data["story_lines_count"] == 1
    assert data["golden_fingers_count"] == 1
    assert data["has_world_view"] is True


@pytest.mark.integration
async def test_get_material_detail_not_found(client: AsyncClient, db_session):
    """Test getting non-existent material returns 403."""
    user, token = await create_test_user(client, db_session, "detailuser2")

    response = await client.get(
        "/api/v1/materials/99999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.integration
async def test_get_material_detail_unauthorized(client: AsyncClient, db_session):
    """Test getting another user's material returns 403."""
    user1, token1 = await create_test_user(client, db_session, "detailuser3")
    user2, _ = await create_test_user(client, db_session, "detailuser4")

    novel = create_test_novel(db_session, user2.id, "User2 Novel")
    create_test_job(db_session, novel.id, "completed")

    response = await client.get(
        f"/api/v1/materials/{novel.id}",
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 403


@pytest.mark.integration
async def test_get_material_detail_deleted(client: AsyncClient, db_session):
    """Test getting soft-deleted material returns 403."""
    from datetime import datetime

    user, token = await create_test_user(client, db_session, "detailuser5")

    novel = create_test_novel(db_session, user.id, "Deleted Novel")
    novel.deleted_at = datetime.utcnow()
    db_session.commit()

    create_test_job(db_session, novel.id, "completed")

    response = await client.get(
        f"/api/v1/materials/{novel.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ==================== Preview & Import Tests ====================


@pytest.mark.integration
async def test_get_relationship_preview_returns_single_entity(client: AsyncClient, db_session):
    """Relationship preview should only include the requested relationship."""
    user, token = await create_test_user(client, db_session, "previewuser1")
    novel = create_test_novel(db_session, user.id, "Preview Novel")
    create_test_job(db_session, novel.id, "completed")

    # Create 3 characters and 2 relationships in the same novel
    c1 = Character(novel_id=novel.id, name="A")
    c2 = Character(novel_id=novel.id, name="B")
    c3 = Character(novel_id=novel.id, name="C")
    db_session.add_all([c1, c2, c3])
    db_session.commit()
    db_session.refresh(c1)
    db_session.refresh(c2)
    db_session.refresh(c3)

    rel1 = CharacterRelationship(
        novel_id=novel.id,
        character_a_id=c1.id,
        character_b_id=c2.id,
        relationship_type="ally",
    )
    rel2 = CharacterRelationship(
        novel_id=novel.id,
        character_a_id=c2.id,
        character_b_id=c3.id,
        relationship_type="enemy",
    )
    db_session.add_all([rel1, rel2])
    db_session.commit()
    db_session.refresh(rel1)

    response = await client.get(
        f"/api/v1/materials/{novel.id}/relationships/{rel1.id}/preview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "A ↔ B"
    assert "A ↔ B" in data["markdown"]
    assert "B ↔ C" not in data["markdown"]


@pytest.mark.integration
async def test_worldview_preview_rejects_mismatched_entity_id(client: AsyncClient, db_session):
    """Worldview preview should enforce entity_id ownership and match."""
    user, token = await create_test_user(client, db_session, "previewuser2")
    novel = create_test_novel(db_session, user.id, "Preview Worldview Novel")
    create_test_job(db_session, novel.id, "completed")

    worldview = WorldView(novel_id=novel.id, power_system="Qi")
    db_session.add(worldview)
    db_session.commit()
    db_session.refresh(worldview)

    response = await client.get(
        f"/api/v1/materials/{novel.id}/worldview/{worldview.id + 1}/preview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_import_material_invalid_target_folder_rejected(client: AsyncClient, db_session):
    """Import should reject invalid target_folder_id."""
    user, token = await create_test_user(client, db_session, "importuser1")
    novel = create_test_novel(db_session, user.id, "Import Novel")
    create_test_job(db_session, novel.id, "completed")

    character = Character(novel_id=novel.id, name="Importer")
    db_session.add(character)

    project = Project(name="Import Project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(character)
    db_session.refresh(project)

    response = await client.post(
        "/api/v1/materials/import",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project.id,
            "novel_id": novel.id,
            "entity_type": "characters",
            "entity_id": character.id,
            "target_folder_id": "non-existent-folder-id",
        },
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_import_material_skips_soft_deleted_auto_folder(client: AsyncClient, db_session):
    """Auto-folder lookup should ignore soft-deleted folders with same title."""
    from models.file_model import File as ProjectFile

    user, token = await create_test_user(client, db_session, "importuser2")
    novel = create_test_novel(db_session, user.id, "Import Novel 2")
    create_test_job(db_session, novel.id, "completed")

    character = Character(novel_id=novel.id, name="Importer2")
    db_session.add(character)

    project = Project(name="Import Project 2", owner_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(character)
    db_session.refresh(project)

    deleted_folder = ProjectFile(
        project_id=project.id,
        title="角色",
        file_type="folder",
        content="",
        is_deleted=True,
    )
    db_session.add(deleted_folder)
    db_session.commit()
    db_session.refresh(deleted_folder)

    response = await client.post(
        "/api/v1/materials/import",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project.id,
            "novel_id": novel.id,
            "entity_type": "characters",
            "entity_id": character.id,
        },
    )

    assert response.status_code == 200
    file_id = response.json()["file_id"]
    imported_file = db_session.get(ProjectFile, file_id)
    assert imported_file is not None
    assert imported_file.parent_id != deleted_folder.id

    new_folder = db_session.get(ProjectFile, imported_file.parent_id)
    assert new_folder is not None
    assert new_folder.title == "角色"
    assert new_folder.is_deleted is False


# ==================== Delete Tests ====================


@pytest.mark.integration
async def test_delete_material_success(client: AsyncClient, db_session):
    """Test successful soft delete of material."""
    user, token = await create_test_user(client, db_session, "deleteuser1")

    novel = create_test_novel(db_session, user.id, "To Delete")
    create_test_job(db_session, novel.id, "completed")

    response = await client.delete(
        f"/api/v1/materials/{novel.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    # Verify soft delete
    db_session.refresh(novel)
    assert novel.deleted_at is not None


@pytest.mark.integration
async def test_delete_material_not_found(client: AsyncClient, db_session):
    """Test deleting non-existent material returns 403."""
    user, token = await create_test_user(client, db_session, "deleteuser2")

    response = await client.delete(
        "/api/v1/materials/99999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.integration
async def test_delete_material_unauthorized(client: AsyncClient, db_session):
    """Test deleting another user's material returns 403."""
    user1, token1 = await create_test_user(client, db_session, "deleteuser3")
    user2, _ = await create_test_user(client, db_session, "deleteuser4")

    novel = create_test_novel(db_session, user2.id, "User2 Novel")
    create_test_job(db_session, novel.id, "completed")

    response = await client.delete(
        f"/api/v1/materials/{novel.id}",
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 403


# ==================== Import Tests ====================


@pytest.mark.integration
async def test_import_material_rejects_invalid_target_folder_id(client: AsyncClient, db_session):
    """Test import endpoint rejects non-existent target folder IDs."""
    user, token = await create_test_user(client, db_session, "importuser11")
    novel = create_test_novel(db_session, user.id, "Import Novel")

    character = Character(novel_id=novel.id, name="Hero")
    db_session.add(character)
    db_session.commit()

    project = Project(name="Import Project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()

    response = await client.post(
        "/api/v1/materials/import",
        json={
            "project_id": project.id,
            "novel_id": novel.id,
            "entity_type": "characters",
            "entity_id": character.id,
            "target_folder_id": "00000000-0000-0000-0000-000000000000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.integration
async def test_import_material_rejects_target_folder_from_other_project(client: AsyncClient, db_session):
    """Test import endpoint rejects target folders that belong to another project."""
    user, token = await create_test_user(client, db_session, "importuser12")
    novel = create_test_novel(db_session, user.id, "Import Novel")

    character = Character(novel_id=novel.id, name="Hero")
    db_session.add(character)
    db_session.commit()

    target_project = Project(name="Target Project", owner_id=user.id)
    other_project = Project(name="Other Project", owner_id=user.id)
    db_session.add_all([target_project, other_project])
    db_session.commit()

    other_project_folder = File(
        project_id=other_project.id,
        title="Characters",
        file_type="folder",
    )
    db_session.add(other_project_folder)
    db_session.commit()

    response = await client.post(
        "/api/v1/materials/import",
        json={
            "project_id": target_project.id,
            "novel_id": novel.id,
            "entity_type": "characters",
            "entity_id": character.id,
            "target_folder_id": other_project_folder.id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.integration
async def test_import_material_rejects_non_folder_target(client: AsyncClient, db_session):
    """Test import endpoint rejects target IDs that are files instead of folders."""
    user, token = await create_test_user(client, db_session, "importuser13")
    novel = create_test_novel(db_session, user.id, "Import Novel")

    character = Character(novel_id=novel.id, name="Hero")
    db_session.add(character)
    db_session.commit()

    project = Project(name="Import Project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()

    non_folder = File(
        project_id=project.id,
        title="Draft File",
        file_type="draft",
        content="content",
    )
    db_session.add(non_folder)
    db_session.commit()

    response = await client.post(
        "/api/v1/materials/import",
        json={
            "project_id": project.id,
            "novel_id": novel.id,
            "entity_type": "characters",
            "entity_id": character.id,
            "target_folder_id": non_folder.id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


# ==================== Authentication Tests ====================


@pytest.mark.integration
async def test_materials_endpoints_require_auth(client: AsyncClient, db_session):
    """Test that all material endpoints require authentication."""
    endpoints = [
        ("GET", "/api/v1/materials"),
        ("GET", "/api/v1/materials/library-summary"),
        ("GET", "/api/v1/materials/search?q=test"),
        ("GET", "/api/v1/materials/1"),
        ("DELETE", "/api/v1/materials/1"),
    ]

    for method, endpoint in endpoints:
        if method == "GET":
            response = await client.get(endpoint)
        elif method == "DELETE":
            response = await client.delete(endpoint)

        assert response.status_code == 401, f"{method} {endpoint} should return 401"
