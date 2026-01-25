"""Tests for Skills System."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from sia.skills import (
    CompositionPlan,
    DiscoveredSkill,
    RetrievedSkill,
    SkillComposer,
    SkillDiscoverer,
    SkillRetriever,
    SkillStorage,
    SkillValidator,
    ValidationResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_llm_router():
    """Create a mock LLM router."""
    router = AsyncMock()
    router.complete = AsyncMock(
        return_value=MagicMock(
            success=True,
            content='{"skills": []}',
        )
    )
    return router


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    service.embed = AsyncMock(
        return_value=MagicMock(embedding=[0.1] * 768, model="nomic-embed-text-v1.5")
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def sample_skill_code():
    """Sample valid skill code."""
    return '''def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    import re
    pattern = r'[\\w.+-]+@[\\w-]+\\.[\\w.-]+'
    return re.findall(pattern, text)
'''


@pytest.fixture
def sample_discovered_skill():
    """Create a sample discovered skill."""
    return DiscoveredSkill(
        name="extract_emails",
        description="Extracts email addresses from text",
        category="data",
        subcategory="parsing",
        tags=["email", "extraction", "regex"],
        code='def extract_emails(text: str) -> list[str]:\n    import re\n    return re.findall(r"[\\w.+-]+@[\\w-]+\\.[\\w.-]+", text)',
        signature="def extract_emails(text: str) -> list[str]",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        output_schema={"type": "array", "items": {"type": "string"}},
        python_dependencies=[],
        source_execution_id=uuid4(),
        extraction_method="llm_extraction",
        confidence=0.8,
    )


# ============================================================================
# DiscoveredSkill Tests
# ============================================================================


class TestDiscoveredSkill:
    """Tests for DiscoveredSkill dataclass."""

    def test_creation_minimal(self):
        """Test creating with minimal fields."""
        skill = DiscoveredSkill(
            name="test_skill",
            description="A test skill",
            category="test",
        )
        assert skill.name == "test_skill"
        assert skill.category == "test"
        assert skill.tags == []
        assert skill.confidence == 0.5

    def test_creation_full(self, sample_discovered_skill):
        """Test creating with all fields."""
        assert sample_discovered_skill.name == "extract_emails"
        assert sample_discovered_skill.category == "data"
        assert "email" in sample_discovered_skill.tags
        assert sample_discovered_skill.confidence == 0.8


# ============================================================================
# SkillDiscoverer Tests
# ============================================================================


class TestSkillDiscoverer:
    """Tests for SkillDiscoverer."""

    def test_init(self, mock_llm_router):
        """Test discoverer initialization."""
        discoverer = SkillDiscoverer(
            llm_router=mock_llm_router,
            min_confidence=0.6,
        )
        assert discoverer.min_confidence == 0.6

    def test_format_steps_empty(self):
        """Test formatting empty steps."""
        discoverer = SkillDiscoverer()
        result = discoverer._format_steps([])
        assert "No intermediate steps" in result

    def test_format_steps_with_data(self):
        """Test formatting steps with data."""
        discoverer = SkillDiscoverer()
        steps = [
            {"action": "search", "result": "found 5 items"},
            {"action": "filter", "result": "kept 3 items"},
        ]
        result = discoverer._format_steps(steps)
        assert "Step 1:" in result
        assert "search" in result
        assert "Step 2:" in result
        assert "filter" in result

    def test_estimate_confidence_with_code(self):
        """Test confidence estimation with valid code."""
        discoverer = SkillDiscoverer()
        skill_data = {
            "code": "def test(): pass",
            "description": "A test function that does something",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "string"},
            "tags": ["test"],
        }
        confidence = discoverer._estimate_confidence(skill_data)
        assert confidence > 0.5  # Should be higher than base

    def test_estimate_confidence_invalid_code(self):
        """Test confidence estimation with invalid code."""
        discoverer = SkillDiscoverer()
        skill_data = {
            "code": "def test( invalid syntax",
            "description": "Short",
        }
        confidence = discoverer._estimate_confidence(skill_data)
        assert confidence < 0.5  # Should be lower due to syntax error

    def test_deduplicate_skills(self, sample_discovered_skill):
        """Test deduplication of skills."""
        discoverer = SkillDiscoverer()

        # Create duplicates
        skill1 = sample_discovered_skill
        skill2 = DiscoveredSkill(
            name="extract_emails_v2",
            description="Another email extractor",
            category="data",
            code=skill1.code,  # Same code
        )
        skill3 = DiscoveredSkill(
            name="different_skill",
            description="Different skill",
            category="web",
            code="def different(): pass",  # Different code
        )

        unique = discoverer._deduplicate_skills([skill1, skill2, skill3])
        assert len(unique) == 2  # skill1 and skill3 (skill2 is duplicate)


# ============================================================================
# SkillStorage Tests
# ============================================================================


class TestSkillStorage:
    """Tests for SkillStorage."""

    def test_init(self, mock_session, mock_embedding_service):
        """Test storage initialization."""
        storage = SkillStorage(
            session=mock_session,
            embedding_service=mock_embedding_service,
            similarity_threshold=0.85,
        )
        assert storage.similarity_threshold == 0.85

    def test_build_embedding_content(self, mock_session, sample_discovered_skill):
        """Test building embedding content."""
        storage = SkillStorage(session=mock_session)
        content = storage._build_embedding_content(sample_discovered_skill)

        assert "extract_emails" in content
        assert "email addresses" in content
        assert "data" in content


# ============================================================================
# SkillRetriever Tests
# ============================================================================


class TestSkillRetriever:
    """Tests for SkillRetriever."""

    def test_init(self, mock_session, mock_embedding_service):
        """Test retriever initialization."""
        retriever = SkillRetriever(
            session=mock_session,
            embedding_service=mock_embedding_service,
            similarity_weight=0.5,
            success_weight=0.35,
            recency_weight=0.15,
        )
        assert retriever.similarity_weight == 0.5
        assert retriever.success_weight == 0.35
        assert retriever.recency_weight == 0.15


# ============================================================================
# RetrievedSkill Tests
# ============================================================================


class TestRetrievedSkill:
    """Tests for RetrievedSkill dataclass."""

    def test_creation(self):
        """Test creating a retrieved skill result."""
        skill = MagicMock()
        result = RetrievedSkill(
            skill=skill,
            similarity_score=0.85,
            success_score=0.9,
            recency_score=0.7,
            combined_score=0.82,
            dependency_count=2,
        )
        assert result.similarity_score == 0.85
        assert result.combined_score == 0.82
        assert result.dependency_count == 2


# ============================================================================
# SkillComposer Tests
# ============================================================================


class TestSkillComposer:
    """Tests for SkillComposer."""

    def test_init(self, mock_session, mock_llm_router):
        """Test composer initialization."""
        composer = SkillComposer(
            session=mock_session,
            llm_router=mock_llm_router,
        )
        assert composer.session == mock_session

    def test_format_skills(self, mock_session):
        """Test formatting skills for prompt."""
        composer = SkillComposer(session=mock_session)

        skills = [
            MagicMock(
                name="skill1",
                description="First skill",
                signature="def skill1(x: int) -> str",
                input_schema={"type": "object"},
                output_schema={"type": "string"},
            ),
            MagicMock(
                name="skill2",
                description="Second skill",
                signature="def skill2(s: str) -> list",
                input_schema={"type": "object"},
                output_schema={"type": "array"},
            ),
        ]

        result = composer._format_skills(skills)
        assert "skill1" in result
        assert "skill2" in result
        assert "First skill" in result

    def test_collect_dependencies(self, mock_session):
        """Test collecting dependencies from skills."""
        composer = SkillComposer(session=mock_session)

        skills = [
            MagicMock(python_dependencies=["requests", "beautifulsoup4"]),
            MagicMock(python_dependencies=["requests", "lxml"]),
        ]

        deps = composer._collect_dependencies(skills)
        assert "requests" in deps
        assert "beautifulsoup4" in deps
        assert "lxml" in deps
        assert len(deps) == 3  # No duplicates


# ============================================================================
# CompositionPlan Tests
# ============================================================================


class TestCompositionPlan:
    """Tests for CompositionPlan dataclass."""

    def test_creation(self):
        """Test creating a composition plan."""
        skills = [MagicMock(), MagicMock()]
        plan = CompositionPlan(
            name="combined_skill",
            description="A combined skill",
            component_skills=skills,
            composition_logic="Sequential execution",
            generated_code="def combined(): pass",
        )
        assert plan.name == "combined_skill"
        assert len(plan.component_skills) == 2
        assert plan.composition_logic == "Sequential execution"


# ============================================================================
# SkillValidator Tests
# ============================================================================


class TestSkillValidator:
    """Tests for SkillValidator."""

    def test_init(self):
        """Test validator initialization."""
        validator = SkillValidator(
            require_type_hints=True,
            require_docstring=True,
            allow_dangerous=False,
        )
        assert validator.require_type_hints is True
        assert validator.require_docstring is True
        assert validator.allow_dangerous is False

    def test_validate_valid_code(self, sample_skill_code):
        """Test validating valid code."""
        validator = SkillValidator()
        result = validator.validate(sample_skill_code)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_syntax_error(self):
        """Test validating code with syntax error."""
        validator = SkillValidator()
        result = validator.validate("def invalid( syntax error")
        assert result.is_valid is False
        assert any("Syntax error" in e for e in result.errors)

    def test_validate_empty_code(self):
        """Test validating empty code."""
        validator = SkillValidator()
        result = validator.validate("")
        assert result.is_valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_validate_dangerous_eval(self):
        """Test detecting dangerous eval."""
        validator = SkillValidator(allow_dangerous=False)
        code = '''def dangerous(x):
    return eval(x)
'''
        result = validator.validate(code)
        assert result.is_valid is False
        assert any("eval" in e.lower() for e in result.errors)

    def test_validate_dangerous_exec(self):
        """Test detecting dangerous exec."""
        validator = SkillValidator(allow_dangerous=False)
        code = '''def dangerous(x):
    exec(x)
'''
        result = validator.validate(code)
        assert result.is_valid is False
        assert any("exec" in e.lower() for e in result.errors)

    def test_validate_allow_dangerous(self):
        """Test allowing dangerous patterns."""
        validator = SkillValidator(allow_dangerous=True, require_docstring=False)
        code = '''def dynamic(x):
    return eval(x)
'''
        result = validator.validate(code)
        assert result.is_valid is True  # Should pass with allow_dangerous

    def test_validate_missing_docstring(self):
        """Test detecting missing docstring."""
        validator = SkillValidator(require_docstring=True)
        code = "def no_docs(x): return x"
        result = validator.validate(code)
        assert result.is_valid is False
        assert any("docstring" in e.lower() for e in result.errors)

    def test_validate_with_docstring(self, sample_skill_code):
        """Test passing with docstring."""
        validator = SkillValidator(require_docstring=True)
        result = validator.validate(sample_skill_code)
        assert result.is_valid is True

    def test_validate_schema_valid(self):
        """Test validating valid schema."""
        validator = SkillValidator()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = validator.validate_schema(schema, "input")
        assert result.is_valid is True

    def test_validate_schema_missing_type(self):
        """Test validating schema missing type."""
        validator = SkillValidator()
        schema = {"properties": {"name": {"type": "string"}}}
        result = validator.validate_schema(schema, "input")
        assert result.is_valid is False
        assert any("type" in e.lower() for e in result.errors)

    def test_get_security_report(self, sample_skill_code):
        """Test generating security report."""
        validator = SkillValidator()
        report = validator.get_security_report(sample_skill_code)

        assert "risk_level" in report
        assert "imports" in report
        assert "dangerous_patterns" in report
        assert report["risk_level"] == "low"  # Safe code


# ============================================================================
# ValidationResult Tests
# ============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation_valid(self):
        """Test creating valid result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_creation_with_errors(self):
        """Test creating result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


# ============================================================================
# Integration Tests (require database)
# ============================================================================


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires database connection",
)
class TestSkillsIntegration:
    """Integration tests requiring actual database."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, db_session):
        """Test storing and retrieving a skill."""
        storage = SkillStorage(session=db_session)

        skill = DiscoveredSkill(
            name="test_integration_skill",
            description="A test skill for integration",
            category="test",
            code="def test(): pass",
        )

        stored, is_new = await storage.store(skill)
        assert is_new is True
        assert stored.name == "test_integration_skill"

        # Retrieve it
        retrieved = await storage.get_by_name("test_integration_skill")
        assert retrieved is not None
        assert retrieved.name == skill.name

        await storage.close()
