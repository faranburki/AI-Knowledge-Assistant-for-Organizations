import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from Backend.Database.mongodb import mongodb
from Backend.core.security import get_current_user
from Backend.Services.rag_pipeline import handle_query
from Backend.ml.classifier import QueryClassifier
from Backend.models.query_log import QueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize classifier (reloaded with fresh 8-class model.pkl)
try:
    classifier = QueryClassifier()
except Exception as _clf_err:
    import logging as _logging
    _logging.getLogger(__name__).warning("ML classifier failed to load: %s", _clf_err)
    classifier = None


class QueryRequest(BaseModel):
    """Request schema for asking a question."""
    question: str
    conversation_id: Optional[str] = None
    top_k: Optional[int] = 8
    org_ids: Optional[List[str]] = None  # public users: subset of subscribed orgs


class QueryHistoryItem(BaseModel):
    """Single query history item."""
    query_id: str
    question: str
    answer: str
    category: str
    timestamp: str
    response_time_ms: int
    sources: Optional[List[dict]] = None


@router.post("/ask", response_model=QueryResponse, tags=["query"])
async def ask_question(
    http_request: Request,
    query_request: QueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Ask a question and get an answer from the RAG pipeline."""
    try:
        if not query_request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty",
            )

        user_id = current_user.get("user_id")
        role = current_user.get("role") or ("org_member" if current_user.get("organization_id") else "public_user")
        embedding_model = http_request.app.state.embedding_model

        org_id = None
        org_ids = None
        subscribed_org_ids = current_user.get("subscribed_org_ids") or []

        if role == "public_user":
            requested = query_request.org_ids or subscribed_org_ids
            if not requested:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subscribe to at least one organization or provide org_ids",
                )
            invalid = set(requested) - set(subscribed_org_ids)
            if invalid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not subscribed to organization(s): {', '.join(sorted(invalid))}",
                )
            org_ids = requested
        else:
            org_id = current_user.get("organization_id")
            if not org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User has no associated organization",
                )

        logger.info(
            "Processing query '%s' for user %s role=%s scope=%s (convo: %s)",
            query_request.question[:50],
            user_id,
            role,
            org_id or org_ids,
            query_request.conversation_id,
        )

        result = await handle_query(
            question=query_request.question,
            user_id=user_id,
            embedding_model=embedding_model,
            role=role,
            org_id=org_id,
            org_ids=org_ids,
            subscribed_org_ids=subscribed_org_ids,
            classifier=classifier,
            top_k=query_request.top_k,
            conversation_id=query_request.conversation_id,
        )

        total_time = result["response_time_ms"]
        query_id = f"query_{int(datetime.utcnow().timestamp() * 1000)}"
        convo_id = result.get("conversation_id")

        return QueryResponse(
            query_id=query_id,
            conversation_id=convo_id,
            answer=result["answer"],
            sources=result["sources"],
            category=result["category"],
            confidence=result["confidence"],
            timestamp=datetime.utcnow().isoformat() + "Z",
            response_time_ms=total_time,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing query: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing query",
        )


@router.get("/history", response_model=List[QueryHistoryItem], tags=["query"])
async def get_query_history(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
):
    """Get query conversation history for the current organization and user."""
    try:
        role = current_user.get("role") or ("org_member" if current_user.get("organization_id") else "public_user")
        org_id = current_user.get("organization_id")
        user_id = current_user.get("user_id")

        match_filter = {"user_id": user_id}
        if role != "public_user":
            match_filter["organization_id"] = org_id

        pipeline = [
            {"$match": match_filter},
            {"$project": {
                "question": 1,
                "answer": 1,
                "category": 1,
                "timestamp": 1,
                "response_time_ms": 1,
                "sources": 1,
                "conversation_id": {"$ifNull": ["$conversation_id", {"$toString": "$_id"}]}
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": "$conversation_id",
                "first_question": {"$first": "$question"},
                "latest_answer": {"$last": "$answer"},
                "latest_category": {"$last": "$category"},
                "latest_timestamp": {"$last": "$timestamp"},
                "latest_response_time_ms": {"$last": "$response_time_ms"},
                "latest_sources": {"$last": "$sources"},
            }},
            {"$sort": {"latest_timestamp": -1}},
            {"$limit": limit}
        ]

        cursor = mongodb.db.queries.aggregate(pipeline)
        history_groups = await cursor.to_list(length=limit)

        history = [
            QueryHistoryItem(
                query_id=g["_id"],  # Returns the conversation thread ID
                question=g["first_question"],
                answer=g["latest_answer"],
                category=g.get("latest_category", "general"),
                timestamp=g.get("latest_timestamp", ""),
                response_time_ms=g.get("latest_response_time_ms", 0),
                sources=g.get("latest_sources", []),
            )
            for g in history_groups
        ]

        logger.info("Retrieved %d threaded conversations for org %s, user %s", len(history), org_id, user_id)
        return history
    except Exception as e:
        logger.error("Error fetching query history: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching query history",
        )


@router.get("/conversation/{conversation_id}", response_model=List[QueryHistoryItem], tags=["query"])
async def get_conversation_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all query turns (messages) in a specific conversation thread for the user."""
    try:
        role = current_user.get("role") or ("org_member" if current_user.get("organization_id") else "public_user")
        org_id = current_user.get("organization_id")
        user_id = current_user.get("user_id")

        query_filter = {
            "user_id": user_id,
            "$or": [
                {"conversation_id": conversation_id},
            ]
        }
        if role != "public_user":
            query_filter["organization_id"] = org_id
        if ObjectId.is_valid(conversation_id):
            query_filter["$or"].append({"_id": ObjectId(conversation_id)})

        cursor = mongodb.db.queries.find(query_filter).sort("timestamp", 1)
        queries = await cursor.to_list(length=100)

        messages = [
            QueryHistoryItem(
                query_id=str(q["_id"]),
                question=q["question"],
                answer=q["answer"],
                category=q.get("category", "unknown"),
                timestamp=q.get("timestamp", ""),
                response_time_ms=q.get("response_time_ms", 0),
                sources=q.get("sources", []),
            )
            for q in queries
        ]

        logger.info("Loaded %d messages for conversation %s, user %s", len(messages), conversation_id, user_id)
        return messages
    except Exception as e:
        logger.error("Error fetching conversation messages: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching conversation messages",
        )


class AnalyticsResponse(BaseModel):
    """Analytics summary response."""
    total_queries: int
    category_breakdown: dict
    avg_response_time_ms: float


@router.get("/analytics", response_model=AnalyticsResponse, tags=["query"])
async def get_analytics(current_user: dict = Depends(get_current_user)):
    """Get analytics scoped by role: organization-wide for admins, user-scoped for members."""
    try:
        org_id = current_user.get("organization_id")
        user_id = current_user.get("user_id")
        is_admin = current_user.get("is_admin", False)

        match_filter = {"organization_id": org_id}
        if not is_admin:
            match_filter["user_id"] = user_id

        # Count total queries
        total_queries = await mongodb.db.queries.count_documents(match_filter)

        # Get category breakdown
        pipeline = [
            {"$match": match_filter},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
        category_data = await mongodb.db.queries.aggregate(pipeline).to_list(None)
        category_breakdown = {item["_id"]: item["count"] for item in category_data}

        # Get average response time
        avg_pipeline = [
            {"$match": match_filter},
            {"$group": {"_id": None, "avg_time": {"$avg": "$response_time_ms"}}},
        ]
        avg_data = await mongodb.db.queries.aggregate(avg_pipeline).to_list(None)
        avg_response_time = avg_data[0]["avg_time"] if avg_data else 0.0

        logger.info(
            "Analytics for org %s (user=%s, admin=%s): %d queries, avg time %.0fms",
            org_id,
            user_id if not is_admin else "all",
            is_admin,
            total_queries,
            avg_response_time,
        )

        return AnalyticsResponse(
            total_queries=total_queries,
            category_breakdown=category_breakdown,
            avg_response_time_ms=round(avg_response_time, 2),
        )
    except Exception as e:
        logger.error("Error fetching analytics: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching analytics",
        )


@router.delete("/{id}", status_code=status.HTTP_200_OK, tags=["query"])
async def delete_query_or_conversation(
    id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a query history log item or an entire conversation thread securely for the current user."""
    try:
        role = current_user.get("role") or ("org_member" if current_user.get("organization_id") else "public_user")
        org_id = current_user.get("organization_id")
        user_id = current_user.get("user_id")
        
        delete_filter = {
            "user_id": user_id,
            "$or": [
                {"conversation_id": id},
            ]
        }
        if role != "public_user":
            delete_filter["organization_id"] = org_id
        if ObjectId.is_valid(id):
            delete_filter["$or"].append({"_id": ObjectId(id)})

        result = await mongodb.db.queries.delete_many(delete_filter)
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation or query not found",
            )
            
        logger.info("Deleted %d query/conversation items with ID %s for org %s, user %s", result.deleted_count, id, org_id, user_id)
        return {"status": "success", "message": f"Deleted {result.deleted_count} item(s) successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting query/conversation: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting conversation or query",
        )
