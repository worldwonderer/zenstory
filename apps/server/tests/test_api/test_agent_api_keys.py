"""
Tests for Agent API Key endpoints.

Integration tests for the agent API key management API, covering:
- POST /api/v1/agent-api-keys - Create API Key
- GET /api/v1/agent-api-keys - List API Keys
- GET /api/v1/agent-api-keys/{id} - Get single API Key
- PUT /api/v1/agent-api-keys/{id} - Update API Key
- DELETE /api/v1/agent-api-keys/{id} - Delete API Key
- POST /api/v1/agent-api-keys/{id}/regenerate - Regenerate Key
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from core.error_codes import ErrorCode
from models import User
from models.agent_api_key import AgentApiKey
from services.agent_auth_service import hash_api_key, generate_api_key
from services.core.auth_service import hash_password


@pytest.fixture
async def auth_headers(client: AsyncClient, db_session: Session):
    """Create a verified user and return auth headers."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("testpassword123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Login to get token
    response = await client.post(
        "/api/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        }
    )

    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
async def auth_headers_user2(client: AsyncClient, db_session: Session):
    """Create a second verified user and return auth headers."""
    user = User(
        email="test2@example.com",
        username="testuser2",
        hashed_password=hash_password("testpassword123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    response = await client.post(
        "/api/auth/login",
        data={
            "username": "testuser2",
            "password": "testpassword123",
        }
    )

    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
async def test_api_key(db_session: Session, auth_headers):
    """Create a test API key directly in the database."""
    from sqlalchemy import text as sql_text

    # Get user from DB to get the ID
    user_result = db_session.exec(
        sql_text("SELECT id FROM user WHERE email = 'test@example.com'")
    ).first()
    user_id = user_result[0] if user_result else None

    plain_key = generate_api_key()
    api_key = AgentApiKey(
        user_id=user_id,
        name="Test API Key",
        description="A test key for testing",
        key_prefix=plain_key[:8],
        key_hash=hash_api_key(plain_key),
        scopes=["read", "write", "chat"],
        is_active=True,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return api_key


@pytest.mark.integration
class TestCreateApiKey:
    """Tests for POST /api/v1/agent-api-keys endpoint."""

    async def test_create_api_key_unauthorized(self, client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            json={"name": "Test Key"},
        )
        assert response.status_code == 401

    async def test_create_api_key_success(self, client: AsyncClient, auth_headers):
        """Test successful creation of an API key."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "My API Key",
                "description": "Key for testing",
                "scopes": ["read", "write"],
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == "My API Key"
        assert data["description"] == "Key for testing"
        assert "key" in data  # Full key should be returned on creation
        assert data["key"].startswith("eg_")
        assert data["key_prefix"] == data["key"][:8]
        assert set(data["scopes"]) == {"read", "write"}
        assert data["is_active"] is True
        assert data["expires_at"] is None

    async def test_create_api_key_default_scopes(self, client: AsyncClient, auth_headers):
        """Test that API key is created with default scopes if not specified."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={"name": "Default Scopes Key"},
        )

        assert response.status_code == 201
        data = response.json()
        assert set(data["scopes"]) == {"read", "write", "chat"}

    async def test_create_api_key_with_expiration(self, client: AsyncClient, auth_headers):
        """Test creating an API key with expiration."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "Expiring Key",
                "expires_in_days": 30,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None

    async def test_create_api_key_with_project_ids(self, client: AsyncClient, auth_headers):
        """Test creating an API key with project restrictions."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "Project Restricted Key",
                "project_ids": ["project-1", "project-2"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["project_ids"] == ["project-1", "project-2"]

    async def test_create_api_key_invalid_scope(self, client: AsyncClient, auth_headers):
        """Test that invalid scopes are rejected."""
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "Invalid Scope Key",
                "scopes": ["read", "invalid_scope"],
            },
        )

        assert response.status_code == 400
        payload = response.json()
        assert payload.get("error_code") == ErrorCode.VALIDATION_ERROR
        assert "Invalid scope" in str(payload.get("error_detail", ""))

    async def test_create_api_key_expiration_bounds(self, client: AsyncClient, auth_headers):
        """Test that expiration must be within valid bounds."""
        # Test minimum bound (must be >= 1)
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "Too Short Expiration",
                "expires_in_days": 0,
            },
        )
        assert response.status_code == 422

        # Test maximum bound (must be <= 3650)
        response = await client.post(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
            json={
                "name": "Too Long Expiration",
                "expires_in_days": 4000,
            },
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestListApiKeys:
    """Tests for GET /api/v1/agent-api-keys endpoint."""

    async def test_list_api_keys_unauthorized(self, client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/api/v1/agent-api-keys")
        assert response.status_code == 401

    async def test_list_api_keys_empty(self, client: AsyncClient, auth_headers):
        """Test listing keys when user has none."""
        response = await client.get(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["keys"] == []
        assert data["total"] == 0

    async def test_list_api_keys_success(self, client: AsyncClient, auth_headers, test_api_key):
        """Test listing API keys for a user."""
        response = await client.get(
            "/api/v1/agent-api-keys",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 1
        assert data["total"] == 1
        assert data["keys"][0]["id"] == test_api_key.id
        assert data["keys"][0]["name"] == "Test API Key"
        # Full key should NOT be included in list response
        assert "key" not in data["keys"][0] or data["keys"][0].get("key") is None

    async def test_list_api_keys_filter_by_active(self, client: AsyncClient, auth_headers, db_session: Session):
        """Test filtering API keys by active status."""
        from sqlalchemy import text as sql_text

        # Get user ID
        user_result = db_session.exec(
            sql_text("SELECT id FROM user WHERE email = 'test@example.com'")
        ).first()
        user_id = user_result[0] if user_result else None

        # Create active and inactive keys
        for i, is_active in enumerate([True, False, True]):
            plain_key = generate_api_key()
            key = AgentApiKey(
                user_id=user_id,
                name=f"Key {i}",
                key_prefix=plain_key[:8],
                key_hash=hash_api_key(plain_key),
                scopes=["read"],
                is_active=is_active,
            )
            db_session.add(key)
        db_session.commit()

        # Filter for active only
        response = await client.get(
            "/api/v1/agent-api-keys?is_active=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 2
        assert all(k["is_active"] for k in data["keys"])

        # Filter for inactive only
        response = await client.get(
            "/api/v1/agent-api-keys?is_active=false",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 1
        assert not data["keys"][0]["is_active"]

    async def test_list_api_keys_pagination(self, client: AsyncClient, auth_headers, db_session: Session):
        """Test pagination of API key listing."""
        from sqlalchemy import text as sql_text

        # Get user ID
        user_result = db_session.exec(
            sql_text("SELECT id FROM user WHERE email = 'test@example.com'")
        ).first()
        user_id = user_result[0] if user_result else None

        # Create multiple keys
        for i in range(5):
            plain_key = generate_api_key()
            key = AgentApiKey(
                user_id=user_id,
                name=f"Key {i:02d}",
                key_prefix=plain_key[:8],
                key_hash=hash_api_key(plain_key),
                scopes=["read"],
                is_active=True,
            )
            db_session.add(key)
        db_session.commit()

        # Test limit
        response = await client.get(
            "/api/v1/agent-api-keys?limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 2
        assert data["total"] == 5

        # Test offset
        response = await client.get(
            "/api/v1/agent-api-keys?limit=2&offset=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 2


@pytest.mark.integration
class TestGetApiKey:
    """Tests for GET /api/v1/agent-api-keys/{id} endpoint."""

    async def test_get_api_key_unauthorized(self, client: AsyncClient, test_api_key):
        """Test that unauthenticated requests are rejected."""
        response = await client.get(f"/api/v1/agent-api-keys/{test_api_key.id}")
        assert response.status_code == 401

    async def test_get_api_key_not_found(self, client: AsyncClient, auth_headers):
        """Test getting a non-existent API key."""
        response = await client.get(
            "/api/v1/agent-api-keys/non-existent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_get_api_key_success(self, client: AsyncClient, auth_headers, test_api_key):
        """Test getting a specific API key."""
        response = await client.get(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_api_key.id
        assert data["name"] == "Test API Key"
        assert data["description"] == "A test key for testing"
        assert data["is_active"] is True
        # Full key should NOT be included
        assert "key" not in data or data.get("key") is None

    async def test_get_api_key_not_owner(self, client: AsyncClient, auth_headers_user2, test_api_key):
        """Test that users cannot access other users' API keys."""
        response = await client.get(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers_user2,
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestUpdateApiKey:
    """Tests for PUT /api/v1/agent-api-keys/{id} endpoint."""

    async def test_update_api_key_unauthorized(self, client: AsyncClient, test_api_key):
        """Test that unauthenticated requests are rejected."""
        response = await client.put(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 401

    async def test_update_api_key_not_found(self, client: AsyncClient, auth_headers):
        """Test updating a non-existent API key."""
        response = await client.put(
            "/api/v1/agent-api-keys/non-existent-id",
            headers=auth_headers,
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    async def test_update_api_key_success(self, client: AsyncClient, auth_headers, test_api_key):
        """Test successful update of an API key."""
        response = await client.put(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers,
            json={
                "name": "Updated Key Name",
                "description": "Updated description",
                "scopes": ["read"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Key Name"
        assert data["description"] == "Updated description"
        assert data["scopes"] == ["read"]

    async def test_update_api_key_partial(self, client: AsyncClient, auth_headers, test_api_key):
        """Test partial update of an API key."""
        original_description = test_api_key.description

        response = await client.put(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers,
            json={"name": "Only Name Updated"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name Updated"
        assert data["description"] == original_description

    async def test_update_api_key_not_owner(self, client: AsyncClient, auth_headers_user2, test_api_key):
        """Test that users cannot update other users' API keys."""
        response = await client.put(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers_user2,
            json={"name": "Trying to update"},
        )
        assert response.status_code == 403

    async def test_update_api_key_invalid_scope(self, client: AsyncClient, auth_headers, test_api_key):
        """Test that invalid scopes are rejected during update."""
        response = await client.put(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers,
            json={"scopes": ["invalid_scope"]},
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestDeleteApiKey:
    """Tests for DELETE /api/v1/agent-api-keys/{id} endpoint."""

    async def test_delete_api_key_unauthorized(self, client: AsyncClient, test_api_key):
        """Test that unauthenticated requests are rejected."""
        response = await client.delete(f"/api/v1/agent-api-keys/{test_api_key.id}")
        assert response.status_code == 401

    async def test_delete_api_key_not_found(self, client: AsyncClient, auth_headers):
        """Test deleting a non-existent API key."""
        response = await client.delete(
            "/api/v1/agent-api-keys/non-existent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_delete_api_key_success(self, client: AsyncClient, auth_headers, test_api_key, db_session: Session):
        """Test successful deletion of an API key."""
        key_id = test_api_key.id

        response = await client.delete(
            f"/api/v1/agent-api-keys/{key_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify key is deleted
        deleted_key = db_session.get(AgentApiKey, key_id)
        assert deleted_key is None

    async def test_delete_api_key_not_owner(self, client: AsyncClient, auth_headers_user2, test_api_key):
        """Test that users cannot delete other users' API keys."""
        response = await client.delete(
            f"/api/v1/agent-api-keys/{test_api_key.id}",
            headers=auth_headers_user2,
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestRegenerateApiKey:
    """Tests for POST /api/v1/agent-api-keys/{id}/regenerate endpoint."""

    async def test_regenerate_api_key_unauthorized(self, client: AsyncClient, test_api_key):
        """Test that unauthenticated requests are rejected."""
        response = await client.post(f"/api/v1/agent-api-keys/{test_api_key.id}/regenerate")
        assert response.status_code == 401

    async def test_regenerate_api_key_not_found(self, client: AsyncClient, auth_headers):
        """Test regenerating a non-existent API key."""
        response = await client.post(
            "/api/v1/agent-api-keys/non-existent-id/regenerate",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_regenerate_api_key_success(self, client: AsyncClient, auth_headers, test_api_key, db_session: Session):
        """Test successful regeneration of an API key."""
        old_hash = test_api_key.key_hash
        old_prefix = test_api_key.key_prefix

        response = await client.post(
            f"/api/v1/agent-api-keys/{test_api_key.id}/regenerate",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "key" in data
        assert data["key"].startswith("eg_")

        # Verify key was changed in database
        db_session.refresh(test_api_key)
        assert test_api_key.key_hash != old_hash
        assert test_api_key.key_prefix != old_prefix
        # Request count should be reset
        assert test_api_key.request_count == 0
        assert test_api_key.last_used_at is None

    async def test_regenerate_api_key_not_owner(self, client: AsyncClient, auth_headers_user2, test_api_key):
        """Test that users cannot regenerate other users' API keys."""
        response = await client.post(
            f"/api/v1/agent-api-keys/{test_api_key.id}/regenerate",
            headers=auth_headers_user2,
        )
        assert response.status_code == 403
