"""
Test to verify that the SQL query bug with 'not Model.is_deleted' is fixed.

This test specifically checks the issue introduced by ruff's E712 auto-fix,
which changed 'Model.is_deleted == False' to 'not Model.is_deleted' in SQL queries.
"""

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from models import Project, User
from services.core.auth_service import hash_password


@pytest.mark.integration
async def test_get_projects_excludes_soft_deleted(client: AsyncClient, db_session: Session):
    """Test that GET /projects correctly filters out soft-deleted projects.

    This test verifies the fix for the bug where 'not Project.is_deleted' in SQL
    queries would generate incorrect SQL, causing the query to return no results.
    """
    # Create user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Login
    login_response = await client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "password123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Create 3 projects
    project1 = Project(name="Active Project 1", owner_id=user.id)
    project2 = Project(name="Active Project 2", owner_id=user.id)
    project3 = Project(name="Active Project 3", owner_id=user.id)
    db_session.add(project1)
    db_session.add(project2)
    db_session.add(project3)
    db_session.commit()

    # Get all projects - should return 3
    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3, f"Expected 3 projects, got {len(data)}"

    # Soft delete one project
    project3.is_deleted = True
    db_session.add(project3)
    db_session.commit()

    # Get projects - should return 2 (excluding soft-deleted)
    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2, f"Expected 2 projects (excluding soft-deleted), got {len(data)}"
    assert all(p["name"] != "Active Project 3" for p in data), "Soft-deleted project should not appear"

    # Soft delete another project
    project2.is_deleted = True
    db_session.add(project2)
    db_session.commit()

    # Get projects - should return 1
    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1, f"Expected 1 project, got {len(data)}"
    assert data[0]["name"] == "Active Project 1"

    print("✅ Test passed: SQL query correctly filters soft-deleted projects")
