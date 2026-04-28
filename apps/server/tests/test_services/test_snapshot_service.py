"""
Tests for SnapshotService (VersionService).

Unit tests for the snapshot management service, covering:
- Snapshot creation (project and file-level)
- Snapshot retrieval and listing
- Snapshot rollback and restoration
- Snapshot comparison
- Snapshot cleanup
- Edge cases and error handling
"""

import json
from datetime import datetime

import pytest
from sqlmodel import Session

from models import File, FileVersion, Project, User
from services.features.snapshot_service import VersionService


@pytest.fixture
def snapshot_service():
    """Return VersionService instance."""
    return VersionService()


@pytest.fixture
def test_project_with_files(db_session: Session):
    """Create a test project with files for snapshot testing."""
    # Create user
    user = User(
        email="snapshot@example.com",
        username="snapshotuser",
        hashed_password="hashed_password",
        name="Snapshot User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Create project
    project = Project(
        name="Snapshot Test Project",
        description="A project for snapshot testing",
        owner_id=user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Create files
    file1 = File(
        title="Chapter 1",
        content="Content of chapter 1",
        file_type="draft",
        project_id=project.id,
        user_id=user.id,
    )
    file2 = File(
        title="Chapter 2",
        content="Content of chapter 2",
        file_type="draft",
        project_id=project.id,
        user_id=user.id,
    )
    db_session.add(file1)
    db_session.add(file2)
    db_session.commit()
    db_session.refresh(file1)
    db_session.refresh(file2)

    # Create file versions
    version1 = FileVersion(
        file_id=file1.id,
        project_id=project.id,
        version_number=1,
        content="Content of chapter 1",
        word_count=4,
        char_count=19,
        is_base_version=True,
    )
    version2 = FileVersion(
        file_id=file2.id,
        project_id=project.id,
        version_number=1,
        content="Content of chapter 2",
        word_count=4,
        char_count=19,
        is_base_version=True,
    )
    db_session.add(version1)
    db_session.add(version2)
    db_session.commit()

    return {
        "project": project,
        "file1": file1,
        "file2": file2,
        "version1": version1,
        "version2": version2,
    }


@pytest.mark.unit
class TestSnapshotServiceCreateSnapshot:
    """Tests for create_snapshot method."""

    def test_create_project_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test creating a snapshot of an entire project."""
        project = test_project_with_files["project"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session,
            project_id=project.id,
            description="Initial project snapshot",
        )

        assert snapshot.id is not None
        assert snapshot.project_id == project.id
        assert snapshot.file_id is None
        assert snapshot.description == "Initial project snapshot"
        assert snapshot.snapshot_type == "auto"
        assert snapshot.version == 3

        # Verify data structure
        data = json.loads(snapshot.data)
        assert "version" in data
        assert "file_versions" in data
        assert "files_metadata" in data
        assert len(data["file_versions"]) == 2  # Two files

    def test_create_file_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test creating a snapshot of a specific file."""
        file1 = test_project_with_files["file1"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session,
            project_id=file1.project_id,
            file_id=file1.id,
            description="File snapshot",
            snapshot_type="manual",
        )

        assert snapshot.file_id == file1.id
        assert snapshot.snapshot_type == "manual"

        # Verify data structure
        data = json.loads(snapshot.data)
        assert len(data["file_versions"]) == 1  # Only one file
        assert data["file_versions"][0]["file_id"] == file1.id

    def test_create_snapshot_with_deleted_files(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test that deleted files are not included in snapshot."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]
        file2 = test_project_with_files["file2"]

        # Soft delete one file
        file1.is_deleted = True
        db_session.add(file1)
        db_session.commit()

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        data = json.loads(snapshot.data)
        # Only non-deleted files should be included
        assert len(data["file_versions"]) == 1
        assert data["file_versions"][0]["file_id"] == file2.id

    def test_create_snapshot_without_versions(
        self, db_session: Session, snapshot_service
    ):
        """Test creating snapshot for file without versions."""
        # Create user and project
        user = User(
            email="noversion@example.com",
            username="noversion",
            hashed_password="hashed",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        project = Project(name="No Version Project", owner_id=user.id)
        db_session.add(project)
        db_session.commit()

        # Create file without versions
        file = File(
            title="No Version File",
            content="Content",
            file_type="draft",
            project_id=project.id,
            user_id=user.id,
        )
        db_session.add(file)
        db_session.commit()

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Snapshot creation should backfill a baseline file version.
        data = json.loads(snapshot.data)
        assert len(data["file_versions"]) == 1
        assert data["file_versions"][0]["file_id"] == file.id
        assert len(data["files_metadata"]) == 1

    def test_create_snapshot_links_versions(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test that versions are linked to snapshot."""
        project = test_project_with_files["project"]
        version1 = test_project_with_files["version1"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Refresh version from database
        db_session.refresh(version1)
        assert version1.snapshot_id == snapshot.id


@pytest.mark.unit
class TestSnapshotServiceGetSnapshots:
    """Tests for get_snapshots method."""

    def test_get_snapshots_for_project(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test retrieving snapshots for a project."""
        project = test_project_with_files["project"]

        # Create multiple snapshots
        snapshot_service.create_snapshot(session=db_session, project_id=project.id)
        snapshot_service.create_snapshot(session=db_session, project_id=project.id)

        snapshots = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id
        )

        assert len(snapshots) == 2
        # Should be ordered by created_at desc (newest first)
        assert snapshots[0].created_at >= snapshots[1].created_at

    def test_get_snapshots_with_file_filter(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test filtering snapshots by file."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]
        file2 = test_project_with_files["file2"]

        # Create snapshots for different files
        snapshot_service.create_snapshot(
            session=db_session, project_id=project.id, file_id=file1.id
        )
        snapshot_service.create_snapshot(
            session=db_session, project_id=project.id, file_id=file2.id
        )

        # Filter by file1
        snapshots = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id, file_id=file1.id
        )

        assert len(snapshots) == 1
        assert snapshots[0].file_id == file1.id

    def test_get_snapshots_with_pagination(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test pagination of snapshots."""
        project = test_project_with_files["project"]

        # Create multiple snapshots
        for _i in range(5):
            snapshot_service.create_snapshot(
                session=db_session, project_id=project.id
            )

        # Test limit
        snapshots = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id, limit=3
        )
        assert len(snapshots) == 3

        # Test offset
        snapshots = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id, limit=2, offset=2
        )
        assert len(snapshots) == 2

    def test_get_snapshots_empty_list(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test getting snapshots when none exist."""
        project = test_project_with_files["project"]

        snapshots = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id
        )

        assert len(snapshots) == 0
        assert isinstance(snapshots, list)


@pytest.mark.unit
class TestSnapshotServiceGetSnapshot:
    """Tests for get_snapshot method."""

    def test_get_existing_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test retrieving an existing snapshot."""
        project = test_project_with_files["project"]

        created_snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        retrieved_snapshot = snapshot_service.get_snapshot(
            session=db_session, snapshot_id=created_snapshot.id
        )

        assert retrieved_snapshot is not None
        assert retrieved_snapshot.id == created_snapshot.id
        assert retrieved_snapshot.project_id == project.id

    def test_get_nonexistent_snapshot(
        self, db_session: Session, snapshot_service
    ):
        """Test retrieving a snapshot that doesn't exist."""
        snapshot = snapshot_service.get_snapshot(
            session=db_session, snapshot_id="nonexistent-id"
        )

        assert snapshot is None


@pytest.mark.unit
class TestSnapshotServiceUpdateDescription:
    """Tests for update_description method."""

    def test_update_snapshot_description(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test updating snapshot description."""
        project = test_project_with_files["project"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session,
            project_id=project.id,
            description="Original description",
        )

        updated_snapshot = snapshot_service.update_description(
            session=db_session,
            snapshot_id=snapshot.id,
            description="Updated description",
        )

        assert updated_snapshot.description == "Updated description"

    def test_update_nonexistent_snapshot_description(
        self, db_session: Session, snapshot_service
    ):
        """Test updating description for nonexistent snapshot."""
        with pytest.raises(ValueError, match="Snapshot .* not found"):
            snapshot_service.update_description(
                session=db_session,
                snapshot_id="nonexistent-id",
                description="New description",
            )


@pytest.mark.unit
class TestSnapshotServiceRollback:
    """Tests for rollback_to_snapshot method."""

    def test_rollback_to_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test rolling back to a previous snapshot."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]

        # Create initial snapshot
        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Modify file content
        file1.content = "Modified content"
        db_session.add(file1)
        db_session.commit()

        # Rollback
        result = snapshot_service.rollback_to_snapshot(
            session=db_session, snapshot_id=snapshot.id
        )

        assert "snapshot_id" in result
        assert "pre_rollback_snapshot_id" in result
        assert "restored" in result
        assert result["snapshot_id"] == snapshot.id
        assert result["restored"]["files"] == 2  # Two files restored

        # Verify file content is restored
        db_session.refresh(file1)
        assert file1.content == "Content of chapter 1"

    def test_rollback_creates_pre_rollback_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test that rollback creates a pre-rollback snapshot."""
        project = test_project_with_files["project"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        result = snapshot_service.rollback_to_snapshot(
            session=db_session, snapshot_id=snapshot.id
        )

        # Verify pre-rollback snapshot was created
        pre_rollback = snapshot_service.get_snapshot(
            session=db_session, snapshot_id=result["pre_rollback_snapshot_id"]
        )
        assert pre_rollback is not None
        assert pre_rollback.snapshot_type == "pre_rollback"
        assert "Before rollback" in pre_rollback.description

    def test_project_rollback_soft_deletes_files_not_in_snapshot(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Full-project rollback should soft-delete files created after snapshot."""
        project = test_project_with_files["project"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Create a new file after snapshot
        extra_file = File(
            title="Added Later",
            content="Added after snapshot",
            file_type="draft",
            project_id=project.id,
            user_id=project.owner_id,
        )
        db_session.add(extra_file)
        db_session.commit()
        db_session.refresh(extra_file)

        extra_version = FileVersion(
            file_id=extra_file.id,
            project_id=project.id,
            version_number=1,
            content=extra_file.content,
            word_count=3,
            char_count=len(extra_file.content),
            is_base_version=True,
        )
        db_session.add(extra_version)
        db_session.commit()

        result = snapshot_service.rollback_to_snapshot(
            session=db_session, snapshot_id=snapshot.id
        )

        db_session.refresh(extra_file)
        assert extra_file.is_deleted is True
        assert result["restored"]["deleted_extra_files"] == 1

    def test_file_scoped_rollback_does_not_delete_unrelated_files(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """File-scoped rollback should not touch unrelated project files."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]
        file2 = test_project_with_files["file2"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id, file_id=file1.id
        )

        # Add another file after snapshot to ensure file-scoped rollback won't delete it.
        extra_file = File(
            title="Another File",
            content="Another content",
            file_type="draft",
            project_id=project.id,
            user_id=project.owner_id,
        )
        db_session.add(extra_file)
        db_session.commit()
        db_session.refresh(extra_file)

        # Modify the target file so rollback has work to do.
        file1.content = "Modified file1 content"
        db_session.add(file1)
        db_session.commit()

        result = snapshot_service.rollback_to_snapshot(
            session=db_session, snapshot_id=snapshot.id
        )

        db_session.refresh(file2)
        db_session.refresh(extra_file)
        assert file2.is_deleted is False
        assert extra_file.is_deleted is False
        assert result["restored"]["files"] == 1
        assert result["restored"]["deleted_extra_files"] == 0

    def test_rollback_restores_parent_and_undeletes_file(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Rollback should restore parent_id and undelete files included in snapshot."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]

        folder = File(
            title="Folder",
            content="",
            file_type="folder",
            project_id=project.id,
            user_id=project.owner_id,
        )
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        # Capture desired hierarchy in snapshot metadata.
        file1.parent_id = folder.id
        db_session.add(file1)
        db_session.commit()

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Break hierarchy and soft-delete before rollback.
        file1.parent_id = None
        file1.content = "Changed after snapshot"
        file1.is_deleted = True
        db_session.add(file1)
        db_session.commit()

        result = snapshot_service.rollback_to_snapshot(
            session=db_session, snapshot_id=snapshot.id
        )

        db_session.refresh(file1)
        assert file1.is_deleted is False
        assert file1.parent_id == folder.id
        assert file1.content == "Content of chapter 1"
        assert result["restored"]["undeleted_files"] >= 1
        assert result["restored"]["restore_versions"] >= 1

    def test_rollback_nonexistent_snapshot(
        self, db_session: Session, snapshot_service
    ):
        """Test rollback to nonexistent snapshot."""
        with pytest.raises(ValueError, match="Snapshot .* not found"):
            snapshot_service.rollback_to_snapshot(
                session=db_session, snapshot_id="nonexistent-id"
            )


@pytest.mark.unit
class TestSnapshotServiceCompareSnapshots:
    """Tests for compare_snapshots method."""

    def test_compare_snapshots_with_changes(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test comparing two snapshots with changes."""
        project = test_project_with_files["project"]
        file1 = test_project_with_files["file1"]

        # Create first snapshot
        snapshot1 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Create a new version for file1
        new_version = FileVersion(
            file_id=file1.id,
            project_id=project.id,
            version_number=2,
            content="New content for chapter 1",
            word_count=5,
            char_count=23,
            is_base_version=False,
        )
        db_session.add(new_version)
        db_session.commit()

        # Create second snapshot
        snapshot2 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Compare
        comparison = snapshot_service.compare_snapshots(
            session=db_session, snapshot1=snapshot1, snapshot2=snapshot2
        )

        assert "snapshot1" in comparison
        assert "snapshot2" in comparison
        assert "changes" in comparison
        assert comparison["snapshot1"]["id"] == snapshot1.id
        assert comparison["snapshot2"]["id"] == snapshot2.id

        # Should have modified file
        assert len(comparison["changes"]["modified"]) == 1
        assert comparison["changes"]["modified"][0]["file_id"] == file1.id

    def test_compare_snapshots_auto_sort(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test that compare_snapshots auto-sorts by timestamp."""
        project = test_project_with_files["project"]

        snapshot1 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )
        snapshot2 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Pass in reverse order (newest first)
        comparison = snapshot_service.compare_snapshots(
            session=db_session, snapshot1=snapshot2, snapshot2=snapshot1
        )

        # Should auto-sort so snapshot1 is the older one
        assert comparison["snapshot1"]["id"] == snapshot1.id
        assert comparison["snapshot2"]["id"] == snapshot2.id

    def test_compare_snapshots_by_id(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test comparing snapshots by ID instead of object."""
        project = test_project_with_files["project"]

        snapshot1 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )
        snapshot2 = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        # Use IDs instead of objects
        comparison = snapshot_service.compare_snapshots(
            session=db_session, snapshot_id_1=snapshot1.id, snapshot_id_2=snapshot2.id
        )

        assert comparison["snapshot1"]["id"] == snapshot1.id
        assert comparison["snapshot2"]["id"] == snapshot2.id

    def test_compare_snapshots_nonexistent(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test comparing with nonexistent snapshot."""
        project = test_project_with_files["project"]

        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )

        with pytest.raises(ValueError, match="One or both snapshots not found"):
            snapshot_service.compare_snapshots(
                session=db_session,
                snapshot1=snapshot,
                snapshot2=None,
                snapshot_id_2="nonexistent-id",
            )


@pytest.mark.unit
class TestSnapshotServiceCleanup:
    """Tests for cleanup_old_snapshots method."""

    def test_cleanup_old_snapshots(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test cleaning up old snapshots based on keep_recent."""
        from datetime import timedelta

        project = test_project_with_files["project"]

        # Create old snapshots (all older than 30 days)
        for _i in range(5):
            snapshot = snapshot_service.create_snapshot(
                session=db_session, project_id=project.id
            )
            snapshot.created_at = datetime.utcnow() - timedelta(days=40)
            db_session.add(snapshot)
            db_session.commit()

        # Create recent snapshots (within 30 days)
        for _i in range(3):
            snapshot_service.create_snapshot(
                session=db_session, project_id=project.id
            )

        # Cleanup with keep_recent=2 and keep_days=30
        # This will delete old snapshots that are older than 30 days, but keep the most recent 2 old snapshots
        deleted_count = snapshot_service.cleanup_old_snapshots(
            session=db_session, project_id=project.id, keep_recent=2, keep_days=30
        )

        # Should delete 3 old snapshots (5 old - 2 kept = 3)
        assert deleted_count == 3

        # Verify remaining snapshots: 2 old + 3 recent = 5 total
        remaining = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id
        )
        assert len(remaining) == 5

    def test_cleanup_by_date(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test cleaning up snapshots by date."""
        from datetime import timedelta

        project = test_project_with_files["project"]

        # Create an old snapshot by manipulating created_at
        snapshot = snapshot_service.create_snapshot(
            session=db_session, project_id=project.id
        )
        snapshot.created_at = datetime.utcnow() - timedelta(days=40)
        db_session.add(snapshot)
        db_session.commit()

        # Create recent snapshot
        snapshot_service.create_snapshot(session=db_session, project_id=project.id)

        # Cleanup snapshots older than 30 days (keeping 0 most recent)
        deleted_count = snapshot_service.cleanup_old_snapshots(
            session=db_session, project_id=project.id, keep_recent=0, keep_days=30
        )

        # Should delete 1 old snapshot
        assert deleted_count == 1

    def test_cleanup_respects_both_criteria(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test that cleanup respects both keep_recent and keep_days."""
        from datetime import timedelta

        project = test_project_with_files["project"]

        # Create old snapshots
        for _i in range(5):
            snapshot = snapshot_service.create_snapshot(
                session=db_session, project_id=project.id
            )
            snapshot.created_at = datetime.utcnow() - timedelta(days=40)
            db_session.add(snapshot)
            db_session.commit()

        # Create recent snapshots
        for _i in range(3):
            snapshot_service.create_snapshot(
                session=db_session, project_id=project.id
            )

        # Cleanup with keep_recent=2 and keep_days=30
        # Old snapshots don't meet date criteria but the most recent 2 are kept
        deleted_count = snapshot_service.cleanup_old_snapshots(
            session=db_session, project_id=project.id, keep_recent=2, keep_days=30
        )

        # Should delete 3 out of 5 old snapshots (keep the most recent 2)
        assert deleted_count == 3

        # Verify remaining: 2 old + 3 recent = 5 total
        remaining = snapshot_service.get_snapshots(
            session=db_session, project_id=project.id
        )
        assert len(remaining) == 5

    def test_cleanup_empty_project(
        self, db_session: Session, snapshot_service, test_project_with_files
    ):
        """Test cleanup when project has no snapshots."""
        project = test_project_with_files["project"]

        deleted_count = snapshot_service.cleanup_old_snapshots(
            session=db_session, project_id=project.id
        )

        assert deleted_count == 0
