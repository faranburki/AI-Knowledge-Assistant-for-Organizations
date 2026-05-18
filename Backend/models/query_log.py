from pydantic import BaseModel
from typing import Optional, List


class QueryLogEntry(BaseModel):
    """Schema for query logging."""
    question: str
    answer: str
    category: str
    sources: List[dict]
    response_time_ms: int


class QueryResponse(BaseModel):
    """Schema for query response."""
    query_id: str
    conversation_id: Optional[str] = None
    answer: str
    sources: List[dict]
    category: str
    confidence: float
    timestamp: str
    response_time_ms: int
