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



_mock_mongodb = ModuleType("Backend.Database.mongodb")
_mock_mongodb.mongodb = MagicMock()
sys.modules["Backend.Database.mongodb"] = _mock_mongodb

# Minimal chromadb stub
if "chromadb" not in sys.modules:
    cdb = ModuleType("chromadb")
    cdb_config = ModuleType("chromadb.config")
    cdb_config.Settings = MagicMock()
    cdb.config = cdb_config
    sys.modules["chromadb"] = cdb
    sys.modules["chromadb.config"] = cdb_config

_mock_chroma_db = ModuleType("Backend.Database.chroma")
_mock_chroma_db.collection = MagicMock()
_mock_chroma_db.COLLECTION_NAME = "documents_chunks"
sys.modules["Backend.Database.chroma"] = _mock_chroma_db

from Backend.Services.embedding_service import (  # noqa: E402
    update_document_status_in_chroma,
)
from Backend.Services.rag_pipeline import (  # noqa: E402
    build_retrieval_filter,
    retrieve_chunks,
)


class TestBuildRetrievalFilter:
    def test_org_member_filters_by_organization_only(self):
        filt = build_retrieval_filter(role="org_member", org_id="org_abc")
        assert filt == {"organization_id": {"$eq": "org_abc"}}

    def test_org_member_without_org_returns_none(self):
        assert build_retrieval_filter(role="org_member", org_id=None) is None

    def test_public_user_filters_orgs_and_public_status(self):
        filt = build_retrieval_filter(
            role="public_user",
            org_ids=["org1", "org2"],
            subscribed_org_ids=["org1", "org2", "org3"],
        )
        assert filt == {
            "$and": [
                {"organization_id": {"$in": ["org1", "org2"]}},
                {"status": {"$eq": "public"}},
            ]
        }

    def test_public_user_defaults_to_subscribed_orgs(self):
        filt = build_retrieval_filter(
            role="public_user",
            subscribed_org_ids=["org_a"],
        )
        assert filt["$and"][0]["organization_id"]["$in"] == ["org_a"]

    def test_public_user_with_no_orgs_returns_none(self):
        assert build_retrieval_filter(role="public_user") is None


@pytest.mark.asyncio
async def test_retrieve_chunks_public_user_applies_public_filter():
    mock_results = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{
            "document_id": "doc1",
            "chunk_index": 1,
            "source_name": "file.pdf",
            "status": "public",
        }]],
        "documents": [["public content"]]
    }

    with patch("Backend.Services.rag_pipeline.chroma") as mock_chroma:
        mock_chroma.collection.query.return_value = mock_results

        chunks = await retrieve_chunks(
            query_vector=[0.1] * 384,
            role="public_user",
            org_ids=["org1"],
            subscribed_org_ids=["org1"],
        )

        assert len(chunks) == 1
        filt = mock_chroma.collection.query.call_args.kwargs["where"]
        assert filt["$and"][1]["status"]["$eq"] == "public"


@pytest.mark.asyncio
async def test_retrieve_chunks_org_member_no_status_filter():
    mock_results = {
        "ids": [[]],
        "distances": [[]],
        "metadatas": [[]],
        "documents": [[]]
    }

    with patch("Backend.Services.rag_pipeline.chroma") as mock_chroma:
        mock_chroma.collection.query.return_value = mock_results

        await retrieve_chunks(
            query_vector=[0.1] * 384,
            role="org_member",
            org_id="org_workspace",
        )

        filt = mock_chroma.collection.query.call_args.kwargs["where"]
        assert filt == {"organization_id": {"$eq": "org_workspace"}}


@pytest.mark.asyncio
async def test_update_document_status_in_chroma():
    with patch("Backend.Services.embedding_service.chroma") as mock_chroma:
        mock_chroma.collection.get.return_value = {
            "ids": ["id1"],
            "metadatas": [{"status": "private", "is_public": False}]
        }
        
        await update_document_status_in_chroma("doc_123", "public")

        call_kwargs = mock_chroma.collection.update.call_args.kwargs
        assert call_kwargs["metadatas"] == [{"status": "public", "is_public": True}]
