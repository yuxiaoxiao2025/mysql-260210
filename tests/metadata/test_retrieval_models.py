"""Tests for RetrievalModels in the metadata knowledge graph system."""

import pytest

from src.metadata.retrieval_models import (
    RetrievalLevel,
    RetrievalRequest,
    TableMatch,
    FieldMatch,
    TableRetrievalResult,
    FieldRetrievalResult,
)


class TestRetrievalLevel:
    """Test cases for RetrievalLevel enum."""

    def test_table_level(self):
        """Test TABLE level value."""
        assert RetrievalLevel.TABLE.value == "table"

    def test_field_level(self):
        """Test FIELD level value."""
        assert RetrievalLevel.FIELD.value == "field"

    def test_all_levels_defined(self):
        """Test all expected levels are defined."""
        levels = [level.value for level in RetrievalLevel]
        assert "table" in levels
        assert "field" in levels


class TestRetrievalRequest:
    """Test cases for RetrievalRequest model."""

    def test_create_request_with_required_fields(self):
        """Test creating RetrievalRequest with only required fields."""
        request = RetrievalRequest(query="查找用户表")

        assert request.query == "查找用户表"
        assert request.level == RetrievalLevel.TABLE
        assert request.top_k == 5
        assert request.filter_tables is None

    def test_create_request_with_all_fields(self):
        """Test creating RetrievalRequest with all fields."""
        request = RetrievalRequest(
            query="查找字段",
            level=RetrievalLevel.FIELD,
            top_k=10,
            filter_tables=["users", "orders"],
        )

        assert request.query == "查找字段"
        assert request.level == RetrievalLevel.FIELD
        assert request.top_k == 10
        assert request.filter_tables == ["users", "orders"]

    def test_top_k_minimum_value(self):
        """Test top_k minimum value is enforced."""
        with pytest.raises(ValueError):
            RetrievalRequest(query="test", top_k=0)

    def test_top_k_maximum_value(self):
        """Test top_k maximum value is enforced."""
        with pytest.raises(ValueError):
            RetrievalRequest(query="test", top_k=25)

    def test_top_k_valid_range(self):
        """Test top_k accepts valid range."""
        request_min = RetrievalRequest(query="test", top_k=1)
        request_max = RetrievalRequest(query="test", top_k=20)

        assert request_min.top_k == 1
        assert request_max.top_k == 20


class TestTableMatch:
    """Test cases for TableMatch model."""

    def test_create_table_match_with_required_fields(self):
        """Test creating TableMatch with required fields."""
        match = TableMatch(
            table_name="users",
            similarity_score=0.85,
            description="User information table",
        )

        assert match.table_name == "users"
        assert match.similarity_score == 0.85
        assert match.description == "User information table"
        assert match.business_tags == []
        assert match.database_name == ""

    def test_create_table_match_with_all_fields(self):
        """Test creating TableMatch with all fields."""
        match = TableMatch(
            table_name="users",
            similarity_score=0.95,
            description="User table",
            business_tags=["用户", "VIP"],
            database_name="mydb",
        )

        assert match.table_name == "users"
        assert match.similarity_score == 0.95
        assert match.description == "User table"
        assert "用户" in match.business_tags
        assert match.database_name == "mydb"

    def test_table_match_serialization(self):
        """Test TableMatch can be serialized."""
        match = TableMatch(
            table_name="orders",
            similarity_score=0.75,
            description="Order table",
            business_tags=["订单"],
        )

        data = match.model_dump()

        assert data["table_name"] == "orders"
        assert data["similarity_score"] == 0.75
        assert data["description"] == "Order table"
        assert data["business_tags"] == ["订单"]


class TestFieldMatch:
    """Test cases for FieldMatch model."""

    def test_create_field_match_with_required_fields(self):
        """Test creating FieldMatch with required fields."""
        match = FieldMatch(
            table_name="users",
            field_name="email",
            data_type="VARCHAR(255)",
            description="Email address",
            similarity_score=0.90,
        )

        assert match.table_name == "users"
        assert match.field_name == "email"
        assert match.data_type == "VARCHAR(255)"
        assert match.description == "Email address"
        assert match.similarity_score == 0.90
        assert match.is_primary_key is False
        assert match.is_foreign_key is False

    def test_create_field_match_with_all_fields(self):
        """Test creating FieldMatch with all fields."""
        match = FieldMatch(
            table_name="orders",
            field_name="user_id",
            data_type="INT",
            description="Foreign key to users",
            similarity_score=0.88,
            is_primary_key=False,
            is_foreign_key=True,
        )

        assert match.table_name == "orders"
        assert match.field_name == "user_id"
        assert match.is_primary_key is False
        assert match.is_foreign_key is True

    def test_field_match_primary_key(self):
        """Test FieldMatch for primary key field."""
        match = FieldMatch(
            table_name="users",
            field_name="id",
            data_type="INT",
            description="Primary key",
            similarity_score=0.95,
            is_primary_key=True,
        )

        assert match.is_primary_key is True

    def test_field_match_serialization(self):
        """Test FieldMatch can be serialized."""
        match = FieldMatch(
            table_name="products",
            field_name="price",
            data_type="DECIMAL(10,2)",
            description="Product price",
            similarity_score=0.80,
        )

        data = match.model_dump()

        assert data["table_name"] == "products"
        assert data["field_name"] == "price"
        assert data["data_type"] == "DECIMAL(10,2)"


class TestTableRetrievalResult:
    """Test cases for TableRetrievalResult model."""

    def test_create_result_with_required_fields(self):
        """Test creating TableRetrievalResult with required fields."""
        matches = [
            TableMatch(
                table_name="users",
                similarity_score=0.9,
                description="User table",
            )
        ]
        result = TableRetrievalResult(
            query="查找用户",
            matches=matches,
            execution_time_ms=50,
        )

        assert result.query == "查找用户"
        assert len(result.matches) == 1
        assert result.execution_time_ms == 50
        assert result.metadata == {}

    def test_create_result_with_metadata(self):
        """Test creating TableRetrievalResult with metadata."""
        matches = []
        result = TableRetrievalResult(
            query="test",
            matches=matches,
            execution_time_ms=10,
            metadata={
                "expanded_tables": ["users", "departments"],
                "total_matches": 5,
            },
        )

        assert result.metadata["expanded_tables"] == ["users", "departments"]
        assert result.metadata["total_matches"] == 5

    def test_empty_matches(self):
        """Test TableRetrievalResult with no matches."""
        result = TableRetrievalResult(
            query="nonexistent",
            matches=[],
            execution_time_ms=5,
        )

        assert len(result.matches) == 0


class TestFieldRetrievalResult:
    """Test cases for FieldRetrievalResult model."""

    def test_create_result_with_required_fields(self):
        """Test creating FieldRetrievalResult with required fields."""
        matches = [
            FieldMatch(
                table_name="users",
                field_name="email",
                data_type="VARCHAR",
                description="Email",
                similarity_score=0.85,
            )
        ]
        result = FieldRetrievalResult(
            query="查找邮箱",
            matches=matches,
            execution_time_ms=30,
        )

        assert result.query == "查找邮箱"
        assert len(result.matches) == 1
        assert result.execution_time_ms == 30
        assert result.metadata == {}

    def test_create_result_with_metadata(self):
        """Test creating FieldRetrievalResult with metadata."""
        result = FieldRetrievalResult(
            query="test",
            matches=[],
            execution_time_ms=10,
            metadata={
                "filter_tables": ["users"],
                "total_matches": 0,
            },
        )

        assert result.metadata["filter_tables"] == ["users"]

    def test_multiple_matches(self):
        """Test FieldRetrievalResult with multiple matches."""
        matches = [
            FieldMatch(
                table_name="users",
                field_name="email",
                data_type="VARCHAR",
                description="Email",
                similarity_score=0.9,
            ),
            FieldMatch(
                table_name="customers",
                field_name="email",
                data_type="VARCHAR",
                description="Customer email",
                similarity_score=0.85,
            ),
        ]
        result = FieldRetrievalResult(
            query="email",
            matches=matches,
            execution_time_ms=25,
        )

        assert len(result.matches) == 2
        assert result.matches[0].table_name == "users"
        assert result.matches[1].table_name == "customers"


class TestRetrievalResultUnion:
    """Test cases for RetrievalResult union type."""

    def test_table_result_is_valid(self):
        """Test TableRetrievalResult is a valid RetrievalResult."""
        result: TableRetrievalResult = TableRetrievalResult(
            query="test",
            matches=[],
            execution_time_ms=10,
        )

        # Should be valid
        assert hasattr(result, "matches")
        assert hasattr(result, "execution_time_ms")

    def test_field_result_is_valid(self):
        """Test FieldRetrievalResult is a valid RetrievalResult."""
        result: FieldRetrievalResult = FieldRetrievalResult(
            query="test",
            matches=[],
            execution_time_ms=10,
        )

        # Should be valid
        assert hasattr(result, "matches")
        assert hasattr(result, "execution_time_ms")

    def test_result_types_are_distinct(self):
        """Test that table and field results can be distinguished."""
        table_result = TableRetrievalResult(
            query="test",
            matches=[
                TableMatch(
                    table_name="users",
                    similarity_score=0.9,
                    description="User table",
                )
            ],
            execution_time_ms=10,
        )

        field_result = FieldRetrievalResult(
            query="test",
            matches=[
                FieldMatch(
                    table_name="users",
                    field_name="id",
                    data_type="INT",
                    description="ID",
                    similarity_score=0.9,
                )
            ],
            execution_time_ms=10,
        )

        # Check match types are different
        assert isinstance(table_result.matches[0], TableMatch)
        assert isinstance(field_result.matches[0], FieldMatch)