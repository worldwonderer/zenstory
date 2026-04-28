"""
Tests for data isolation across multi-tenant boundaries.

Verifies that:
1. Vector search results are properly filtered by project_id
2. Context assembler validates project ownership
3. Background indexing worker validates entity ownership
"""
import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from agent.context.assembler import ContextAssembler
from models import File, Project, User
from services.infra.vector_search_service import (
    LlamaIndexService,
    SearchResult,
)


@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="test_users")
def test_users_fixture(session: Session):
    """Create test users."""
    user1 = User(
        id="user1",
        email="user1@example.com",
        username="user1",
        hashed_password="hashed",
    )
    user2 = User(
        id="user2",
        email="user2@example.com",
        username="user2",
        hashed_password="hashed",
    )
    session.add(user1)
    session.add(user2)
    session.commit()
    session.refresh(user1)
    session.refresh(user2)
    return user1, user2


@pytest.fixture(name="test_projects")
def test_projects_fixture(session: Session, test_users):
    """Create test projects for each user."""
    user1, user2 = test_users

    project1 = Project(
        id="project1",
        name="User 1 Project",
        description="User 1 Project",
        owner_id=user1.id,
    )
    project2 = Project(
        id="project2",
        name="User 2 Project",
        description="User 2 Project",
        owner_id=user2.id,
    )
    session.add(project1)
    session.add(project2)
    session.commit()
    session.refresh(project1)
    session.refresh(project2)
    return project1, project2


@pytest.fixture(name="test_files")
def test_files_fixture(session: Session, test_projects):
    """Create test files for each project."""
    project1, project2 = test_projects

    file1 = File(
        id="file1",
        project_id=project1.id,
        title="File 1",
        content="Content for file 1",
        file_type="draft",
        is_deleted=False,
    )
    file2 = File(
        id="file2",
        project_id=project2.id,
        title="File 2",
        content="Content for file 2",
        file_type="draft",
        is_deleted=False,
    )
    session.add(file1)
    session.add(file2)
    session.commit()
    session.refresh(file1)
    session.refresh(file2)
    return file1, file2


class TestVectorSearchIsolation:
    """Tests for vector search data isolation."""

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_valid(self, mock_init, session: Session, test_files):
        """Test that _validate_entity_ownership accepts valid entities."""
        file1, _ = test_files

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=file1.project_id,
            entity_type="draft",
            entity_id=file1.id,
            session=session,
        )
        assert result is True

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_wrong_project(self, mock_init, session: Session, test_files):
        """Test that _validate_entity_ownership rejects entities from wrong project."""
        file1, _ = test_files

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id="wrong_project_id",
            entity_type="draft",
            entity_id=file1.id,
            session=session,
        )
        assert result is False

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_deleted_file(self, mock_init, session: Session, test_files):
        """Test that _validate_entity_ownership rejects deleted files."""
        file1, _ = test_files
        file1.is_deleted = True
        session.add(file1)
        session.commit()

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=file1.project_id,
            entity_type="draft",
            entity_id=file1.id,
            session=session,
        )
        assert result is False

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_nonexistent_file(self, mock_init, session: Session):
        """Test that _validate_entity_ownership rejects nonexistent files."""
        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id="project1",
            entity_type="draft",
            entity_id="nonexistent_file_id",
            session=session,
        )
        assert result is False

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_unknown_entity_type(self, mock_init, session: Session, test_files):
        """Test that _validate_entity_ownership rejects unknown entity types."""
        file1, _ = test_files

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=file1.project_id,
            entity_type="unknown_type",
            entity_id=file1.id,
            session=session,
        )
        assert result is False

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_accepts_document_type(self, mock_init, session: Session, test_projects):
        """Test that _validate_entity_ownership accepts document file type."""
        project1, _ = test_projects
        file_doc = File(
            id="file_document",
            project_id=project1.id,
            title="Doc file",
            content="Document content",
            file_type="document",
            is_deleted=False,
        )
        session.add(file_doc)
        session.commit()

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=project1.id,
            entity_type="document",
            entity_id=file_doc.id,
            session=session,
        )
        assert result is True

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_accepts_script_type(self, mock_init, session: Session, test_projects):
        """Test that _validate_entity_ownership accepts script file type."""
        project1, _ = test_projects
        file_script = File(
            id="file_script",
            project_id=project1.id,
            title="Script file",
            content="Script content",
            file_type="script",
            is_deleted=False,
        )
        session.add(file_script)
        session.commit()

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=project1.id,
            entity_type="script",
            entity_id=file_script.id,
            session=session,
        )
        assert result is True

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_validate_entity_ownership_rejects_entity_type_mismatch(
        self, mock_init, session: Session, test_files
    ):
        """Test that _validate_entity_ownership rejects metadata type mismatch."""
        file1, _ = test_files

        service = LlamaIndexService()
        result = service._validate_entity_ownership(
            project_id=file1.project_id,
            entity_type="character",  # DB type is draft
            entity_id=file1.id,
            session=session,
        )
        assert result is False

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_semantic_search_expands_candidate_window_for_type_filter(
        self, mock_init, session: Session, test_projects, monkeypatch
    ):
        """Test semantic_search retries with larger candidate window when type filter drops initial hits."""
        project1, _ = test_projects
        file_character = File(
            id="file_character",
            project_id=project1.id,
            title="Hero",
            content="Character profile",
            file_type="character",
            is_deleted=False,
        )
        session.add(file_character)
        session.commit()

        service = LlamaIndexService()

        def make_node(entity_type: str, entity_id: str, title: str, text: str, score: float):
            return SimpleNamespace(
                node=SimpleNamespace(
                    metadata={
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "title": title,
                    },
                    text=text,
                ),
                score=score,
            )

        class FakeRetriever:
            def __init__(self, similarity_top_k: int):
                self.similarity_top_k = similarity_top_k

            def retrieve(self, query: str):
                base_nodes = [
                    make_node("draft", "d1", "Draft 1", "draft text 1", 0.95),
                    make_node("draft", "d2", "Draft 2", "draft text 2", 0.94),
                    make_node("draft", "d3", "Draft 3", "draft text 3", 0.93),
                    make_node("draft", "d4", "Draft 4", "draft text 4", 0.92),
                ]
                if self.similarity_top_k <= 4:
                    return base_nodes
                return base_nodes + [
                    make_node("character", "foreign_character", "Foreign", "foreign text", 0.90),
                    make_node("character", file_character.id, "Hero", "character text", 0.89),
                ]

        class FakeIndex:
            def __init__(self):
                self.requested_topk: list[int] = []

            def as_retriever(self, similarity_top_k: int):
                self.requested_topk.append(similarity_top_k)
                return FakeRetriever(similarity_top_k)

        fake_index = FakeIndex()
        service.get_or_create_index = MagicMock(return_value=fake_index)
        service._validate_entity_ownership = MagicMock(
            side_effect=lambda _project_id, _entity_type, entity_id, _session: entity_id != "foreign_character"
        )

        monkeypatch.setattr(
            "database.create_session",
            lambda: contextlib.nullcontext(session),
        )

        results = service.semantic_search(
            project_id=project1.id,
            query="hero",
            top_k=2,
            entity_types=["character"],
        )

        assert fake_index.requested_topk == [4, 8]
        assert len(results) == 1
        assert results[0].entity_id == file_character.id
        validated_ids = [call.args[2] for call in service._validate_entity_ownership.call_args_list]
        assert "foreign_character" in validated_ids

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_hybrid_search_fuses_semantic_and_lexical_results(
        self, mock_init, session: Session, test_projects, monkeypatch
    ):
        """Hybrid search should merge semantic + lexical results and expose dual sources."""
        project1, _ = test_projects
        service = LlamaIndexService()

        service.semantic_search = MagicMock(return_value=[
            SearchResult(
                entity_type="draft",
                entity_id="file_sem_1",
                title="Semantic 1",
                content="hero enters city",
                score=0.92,
                snippet="hero enters city",
                line_start=1,
                fused_score=0.92,
                sources=["semantic"],
            ),
            SearchResult(
                entity_type="draft",
                entity_id="file_sem_2",
                title="Semantic 2",
                content="mentor appears",
                score=0.83,
                snippet="mentor appears",
                line_start=4,
                fused_score=0.83,
                sources=["semantic"],
            ),
        ])
        service._lexical_search = MagicMock(return_value=[
            SearchResult(
                entity_type="draft",
                entity_id="file_sem_1",
                title="Semantic 1",
                content="hero enters city",
                score=4.2,
                snippet="hero enters city",
                line_start=1,
                fused_score=4.2,
                sources=["lexical"],
            ),
            SearchResult(
                entity_type="draft",
                entity_id="file_lex_only",
                title="Lexical Only",
                content="city gate guard",
                score=3.8,
                snippet="city gate guard",
                line_start=8,
                fused_score=3.8,
                sources=["lexical"],
            ),
        ])

        monkeypatch.setattr("database.create_session", lambda: contextlib.nullcontext(session))

        results = service.hybrid_search(
            project_id=project1.id,
            query="hero city",
            top_k=3,
            entity_types=["draft"],
        )

        assert len(results) == 3
        assert results[0].entity_id == "file_sem_1"
        result_map = {r.entity_id: r for r in results}
        assert set(result_map["file_sem_1"].sources) == {"semantic", "lexical"}
        assert result_map["file_lex_only"].sources == ["lexical"]
        assert result_map["file_sem_2"].sources == ["semantic"]
        assert result_map["file_sem_1"].fused_score is not None

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_hybrid_search_remains_active_without_disable_flags(
        self,
        mock_init,
        monkeypatch,
        session: Session,
    ):
        """Hybrid search should remain active when semantic + lexical are both available."""
        service = LlamaIndexService()
        service.semantic_search = MagicMock(return_value=[
            SearchResult(
                entity_type="draft",
                entity_id="file_semantic_and_lexical",
                title="Semantic only",
                content="plot twist",
                score=0.91,
                snippet="plot twist",
                line_start=2,
                sources=["semantic"],
            )
        ])
        service._lexical_search = MagicMock(return_value=[
            SearchResult(
                entity_type="draft",
                entity_id="file_semantic_and_lexical",
                title="Lexical only",
                content="plot twist",
                score=3.2,
                snippet="plot twist",
                line_start=2,
                sources=["lexical"],
            )
        ])

        monkeypatch.setattr("database.create_session", lambda: contextlib.nullcontext(session))

        results = service.hybrid_search(
            project_id="project1",
            query="plot twist",
            top_k=3,
            entity_types=None,
        )

        assert len(results) == 1
        assert set(results[0].sources) == {"semantic", "lexical"}
        service.semantic_search.assert_called_once()
        service._lexical_search.assert_called_once()

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_lexical_search_supports_multi_token_query(self, mock_init, session: Session, test_projects):
        """Lexical search should tokenize query instead of requiring full-phrase contains."""
        project1, _ = test_projects
        file_one = File(
            id="lex_file_1",
            project_id=project1.id,
            title="Hero arrives",
            content="chapter intro",
            file_type="draft",
            is_deleted=False,
        )
        file_two = File(
            id="lex_file_2",
            project_id=project1.id,
            title="City watch",
            content="the city is tense",
            file_type="draft",
            is_deleted=False,
        )
        session.add(file_one)
        session.add(file_two)
        session.commit()

        service = LlamaIndexService()
        results = service._lexical_search(
            session=session,
            project_id=project1.id,
            query="hero city",
            top_k=5,
            entity_types=["draft"],
        )

        result_ids = {r.entity_id for r in results}
        assert file_one.id in result_ids
        assert file_two.id in result_ids

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_lexical_search_skips_oversized_tokens(self, mock_init, session: Session, test_projects):
        """Oversized query tokens should be ignored to avoid excessive OR conditions."""
        project1, _ = test_projects
        file_one = File(
            id="lex_file_guardrail_1",
            project_id=project1.id,
            title="Hero patrol",
            content="hero scouts the old city",
            file_type="draft",
            is_deleted=False,
        )
        session.add(file_one)
        session.commit()

        service = LlamaIndexService()
        long_noise = "x" * 120
        results = service._lexical_search(
            session=session,
            project_id=project1.id,
            query=f"hero {long_noise} hero",
            top_k=5,
            entity_types=["draft"],
        )

        result_ids = {r.entity_id for r in results}
        assert file_one.id in result_ids

    @patch('services.infra.vector_search_service.LlamaIndexService.__init__', return_value=None)
    def test_lexical_search_overlong_single_token_uses_safe_fallback(self, mock_init, session: Session, test_projects):
        """When all tokens are oversized, lexical search should use safe truncated fallback."""
        project1, _ = test_projects
        overlong_prefix = "y" * 40
        file_one = File(
            id="lex_file_guardrail_2",
            project_id=project1.id,
            title="Noise capture",
            content=f"{overlong_prefix} tail",
            file_type="draft",
            is_deleted=False,
        )
        session.add(file_one)
        session.commit()

        service = LlamaIndexService()
        overlong_query = "y" * 120
        results = service._lexical_search(
            session=session,
            project_id=project1.id,
            query=overlong_query,
            top_k=5,
            entity_types=["draft"],
        )

        result_ids = {r.entity_id for r in results}
        assert file_one.id in result_ids

    def test_search_result_to_dict_includes_snippet_fields(self):
        result = SearchResult(
            entity_type="draft",
            entity_id="file1",
            title="Chapter 1",
            content="line1\nline2\nline3",
            score=0.8,
            sources=["semantic"],
        )

        payload = result.to_dict()
        assert "snippet" in payload
        assert "line_start" in payload
        assert "fused_score" in payload
        assert "sources" in payload
        assert payload["fused_score"] == payload["score"]


class TestContextAssemblerIsolation:
    """Tests for Context Assembler data isolation."""

    def test_assemble_with_valid_user(self, session: Session, test_users, test_projects):
        """Test that assemble() succeeds with valid user ownership."""
        user1, _ = test_users
        project1, _ = test_projects

        assembler = ContextAssembler()
        context_data = assembler.assemble(
            session=session,
            project_id=project1.id,
            user_id=user1.id,
            max_tokens=1000,
        )

        # Should return valid context data (not empty due to permission denial)
        assert context_data is not None
        assert isinstance(context_data.context, str)

    def test_assemble_with_wrong_user(self, session: Session, test_users, test_projects):
        """Test that assemble() returns empty context for wrong user."""
        user1, user2 = test_users
        project1, _ = test_projects

        assembler = ContextAssembler()
        context_data = assembler.assemble(
            session=session,
            project_id=project1.id,
            user_id=user2.id,  # Wrong user
            max_tokens=1000,
        )

        # Should return empty context due to permission denial
        assert context_data.context == ""
        assert context_data.items == []
        assert context_data.token_estimate == 0

    def test_assemble_without_user_id(self, session: Session, test_projects):
        """Test that assemble() works without user_id (skips verification)."""
        project1, _ = test_projects

        assembler = ContextAssembler()
        context_data = assembler.assemble(
            session=session,
            project_id=project1.id,
            user_id=None,  # No user verification
            max_tokens=1000,
        )

        # Should return valid context data
        assert context_data is not None
        assert isinstance(context_data.context, str)


class TestBackgroundIndexingIsolation:
    """Tests for background indexing worker data isolation."""

    @patch('services.infra.vector_search_service.get_llama_index_service')
    @patch('database.create_session')
    def test_run_index_upsert_valid_entity(
        self, mock_create_session, mock_get_service, session: Session, test_files, test_projects, test_users
    ):
        """Test that _run_index_upsert processes valid entities."""
        from services.infra.vector_search_service import _run_index_upsert

        file1, _ = test_files
        user1, _ = test_users
        project1, _ = test_projects

        # Verify the session has the test data
        assert session.get(Project, project1.id) is not None
        assert session.get(Project, project1.id).owner_id == user1.id

        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_create_session.return_value.__enter__.return_value = session

        task = {
            "project_id": file1.project_id,
            "entity_type": "draft",
            "entity_id": file1.id,
            "title": file1.title,
            "content": file1.content,
            "user_id": user1.id,
        }

        _run_index_upsert(task)

        # Should call update_entity
        mock_service.update_entity.assert_called_once()

    @patch('services.infra.vector_search_service.get_llama_index_service')
    @patch('database.create_session')
    def test_run_index_upsert_wrong_project(
        self, mock_create_session, mock_get_service, session: Session, test_files
    ):
        """Test that _run_index_upsert skips entities from wrong project."""
        from services.infra.vector_search_service import _run_index_upsert

        file1, _ = test_files
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_create_session.return_value.__enter__.return_value = session

        task = {
            "project_id": "wrong_project_id",
            "entity_type": "draft",
            "entity_id": file1.id,
            "title": file1.title,
            "content": file1.content,
            "user_id": "user1",
        }

        _run_index_upsert(task)

        # Should NOT call update_entity
        mock_service.update_entity.assert_not_called()

    @patch('services.infra.vector_search_service.get_llama_index_service')
    @patch('database.create_session')
    def test_run_index_upsert_deleted_entity(
        self, mock_create_session, mock_get_service, session: Session, test_files
    ):
        """Test that _run_index_upsert skips deleted entities."""
        from services.infra.vector_search_service import _run_index_upsert

        file1, _ = test_files
        file1.is_deleted = True
        session.add(file1)
        session.commit()

        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_create_session.return_value.__enter__.return_value = session

        task = {
            "project_id": file1.project_id,
            "entity_type": "draft",
            "entity_id": file1.id,
            "title": file1.title,
            "content": file1.content,
            "user_id": "user1",
        }

        _run_index_upsert(task)

        # Should NOT call update_entity
        mock_service.update_entity.assert_not_called()

    @patch('services.infra.vector_search_service.get_llama_index_service')
    @patch('database.create_session')
    def test_run_index_upsert_nonexistent_entity(
        self, mock_create_session, mock_get_service, session: Session
    ):
        """Test that _run_index_upsert skips nonexistent entities."""
        from services.infra.vector_search_service import _run_index_upsert

        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_create_session.return_value.__enter__.return_value = session

        task = {
            "project_id": "project1",
            "entity_type": "draft",
            "entity_id": "nonexistent_file_id",
            "title": "Title",
            "content": "Content",
            "user_id": "user1",
        }

        _run_index_upsert(task)

        # Should NOT call update_entity
        mock_service.update_entity.assert_not_called()
