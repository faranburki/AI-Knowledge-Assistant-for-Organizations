"""Unit tests for document privacy and role-based retrieval filters."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy dependencies so rag_pipeline can be imported without motor/groq.
if "motor" not in sys.modules:
    motor = ModuleType("motor")
    motor_mongo = ModuleType("motor.motor_asyncio")
    motor_mongo.AsyncIOMotorClient = MagicMock()
    motor.motor_asyncio = motor_mongo
    sys.modules["motor"] = motor
    sys.modules["motor.motor_asyncio"] = motor_mongo

if "groq" not in sys.modules:
    groq_mod = ModuleType("groq")
    groq_mod.Groq = MagicMock()
    sys.modules["groq"] = groq_mod

_mock_mongodb = ModuleType("Backend.Database.mongodb")
_mock_mongodb.mongodb = MagicMock()
sys.modules["Backend.Database.mongodb"] = _mock_mongodb

# Minimal qdrant_client stub for filter construction in rag_pipeline.
if "qdrant_client" not in sys.modules:
    qc = ModuleType("qdrant_client")
    qc_http = ModuleType("qdrant_client.http")
    qc_models = ModuleType("qdrant_client.http.models")

    class _Filter:
        def __init__(self, must=None):
            self.must = must or []

    class _FieldCondition:
        def __init__(self, key, match):
            self.key = key
            self.match = match

    class _MatchValue:
        def __init__(self, value):
            self.value = value

    class _MatchAny:
        def __init__(self, any):
            self.any = any

    class _PointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    qc_models.Filter = _Filter
    qc_models.FieldCondition = _FieldCondition
    qc_models.MatchValue = _MatchValue
    qc_models.MatchAny = _MatchAny
    qc_models.PointStruct = _PointStruct
    qc.http = qc_http
    qc_http.models = qc_models
    sys.modules["qdrant_client"] = qc
    sys.modules["qdrant_client.http"] = qc_http
    sys.modules["qdrant_client.http.models"] = qc_models

_mock_qdrant_db = ModuleType("Backend.Database.qdrant")
_mock_qdrant_db.client = MagicMock()
_mock_qdrant_db.COLLECTION_NAME = "documents_chunks"
sys.modules["Backend.Database.qdrant"] = _mock_qdrant_db

from qdrant_client.http.models import (  # noqa: E402
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
)

from Backend.Services.embedding_service import (  # noqa: E402
    build_qdrant_points,
    update_document_status_in_qdrant,
)
from Backend.Services.rag_pipeline import (  # noqa: E402
    build_retrieval_filter,
    retrieve_chunks,
)


class TestBuildRetrievalFilter:
    def test_org_member_filters_by_organization_only(self):
        filt = build_retrieval_filter(role="org_member", org_id="org_abc")
        assert isinstance(filt, Filter)
        assert len(filt.must) == 1
        cond = filt.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "organization_id"
        assert isinstance(cond.match, MatchValue)
        assert cond.match.value == "org_abc"

    def test_org_member_without_org_returns_none(self):
        assert build_retrieval_filter(role="org_member", org_id=None) is None

    def test_public_user_filters_orgs_and_public_status(self):
        filt = build_retrieval_filter(
            role="public_user",
            org_ids=["org1", "org2"],
            subscribed_org_ids=["org1", "org2", "org3"],
        )
        assert isinstance(filt, Filter)
        assert len(filt.must) == 2

        org_cond, status_cond = filt.must[0], filt.must[1]
        assert org_cond.key == "organization_id"
        assert isinstance(org_cond.match, MatchAny)
        assert set(org_cond.match.any) == {"org1", "org2"}

        assert status_cond.key == "status"
        assert isinstance(status_cond.match, MatchValue)
        assert status_cond.match.value == "public"

    def test_public_user_defaults_to_subscribed_orgs(self):
        filt = build_retrieval_filter(
            role="public_user",
            subscribed_org_ids=["org_a"],
        )
        assert filt.must[0].match.any == ["org_a"]

    def test_public_user_with_no_orgs_returns_none(self):
        assert build_retrieval_filter(role="public_user") is None


@pytest.mark.asyncio
async def test_retrieve_chunks_public_user_applies_public_filter():
    mock_hit = MagicMock()
    mock_hit.score = 0.9
    mock_hit.payload = {
        "document_id": "doc1",
        "chunk_index": 1,
        "chunk_text": "public content",
        "source_name": "file.pdf",
        "status": "public",
    }
    mock_results = MagicMock()
    mock_results.points = [mock_hit]

    with patch("Backend.Services.rag_pipeline.qdrant") as mock_qdrant:
        mock_qdrant.client.query_points.return_value = mock_results
        mock_qdrant.COLLECTION_NAME = "documents_chunks"

        chunks = await retrieve_chunks(
            query_vector=[0.1] * 384,
            role="public_user",
            org_ids=["org1"],
            subscribed_org_ids=["org1"],
        )

        assert len(chunks) == 1
        filt = mock_qdrant.client.query_points.call_args.kwargs["query_filter"]
        assert filt.must[1].match.value == "public"


@pytest.mark.asyncio
async def test_retrieve_chunks_org_member_no_status_filter():
    mock_results = MagicMock()
    mock_results.points = []

    with patch("Backend.Services.rag_pipeline.qdrant") as mock_qdrant:
        mock_qdrant.client.query_points.return_value = mock_results
        mock_qdrant.COLLECTION_NAME = "documents_chunks"

        await retrieve_chunks(
            query_vector=[0.1] * 384,
            role="org_member",
            org_id="org_workspace",
        )

        filt = mock_qdrant.client.query_points.call_args.kwargs["query_filter"]
        assert len(filt.must) == 1
        assert filt.must[0].key == "organization_id"


def test_embedding_payload_includes_status():
    points = build_qdrant_points(
        chunks=["hello"],
        embeddings=[[0.0] * 384],
        metadata={
            "document_id": "doc_x",
            "organization_id": "org1",
            "status": "private",
        },
    )
    assert points[0].payload["status"] == "private"
    assert points[0].payload["is_public"] is False

    points_public = build_qdrant_points(
        chunks=["hello"],
        embeddings=[[0.0] * 384],
        metadata={"document_id": "doc_y", "status": "public"},
    )
    assert points_public[0].payload["status"] == "public"
    assert points_public[0].payload["is_public"] is True


def test_update_document_status_in_qdrant():
    with patch("Backend.Services.embedding_service.qdrant") as mock_qdrant:
        mock_qdrant.COLLECTION_NAME = "documents_chunks"
        update_document_status_in_qdrant("doc_123", "public")

        call_kwargs = mock_qdrant.client.set_payload.call_args.kwargs
        assert call_kwargs["payload"] == {"status": "public", "is_public": True}
