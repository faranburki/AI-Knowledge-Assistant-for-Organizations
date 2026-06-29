import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from groq import Groq

from Backend.Database.mongodb import mongodb
from Backend.Database import qdrant
from bson import ObjectId

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq client — initialised once at module load.
# The API key is validated; a missing key will log a warning but won't crash
# the import.  Actual failures surface when a query is made.
# ---------------------------------------------------------------------------
_groq_api_key = os.getenv("GROQ_API_KEY")
if not _groq_api_key:
    logger.warning("GROQ_API_KEY is not set — LLM calls will fail at runtime.")

groq_client = Groq(api_key=_groq_api_key)

# Default model — llama-3.1 is available on the free Groq tier
DEFAULT_LLM_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


# ---------------------------------------------------------------------------
# Step 1 — Retrieve relevant chunks from Qdrant
# ---------------------------------------------------------------------------
def build_retrieval_filter(
    role: str,
    org_id: Optional[str] = None,
    org_ids: Optional[List[str]] = None,
    subscribed_org_ids: Optional[List[str]] = None,
):
    """Build a Qdrant filter based on the querying user's role."""
    from qdrant_client.http.models import (
        FieldCondition,
        Filter,
        MatchAny,
        MatchValue,
    )

    if role == "public_user":
        target_orgs = org_ids if org_ids else (subscribed_org_ids or [])
        if not target_orgs:
            return None
        return Filter(
            must=[
                FieldCondition(
                    key="organization_id",
                    match=MatchAny(any=target_orgs),
                ),
                FieldCondition(
                    key="status",
                    match=MatchValue(value="public"),
                ),
            ]
        )

    if not org_id:
        return None

    return Filter(
        must=[
            FieldCondition(
                key="organization_id",
                match=MatchValue(value=org_id),
            )
        ]
    )


async def retrieve_chunks(
    query_vector: List[float],
    role: str = "org_member",
    org_id: Optional[str] = None,
    org_ids: Optional[List[str]] = None,
    subscribed_org_ids: Optional[List[str]] = None,
    top_k: int = 8,
    score_threshold: float = 0.3,
) -> List[Dict]:
    """Retrieve top-k semantically similar chunks with role-based access control."""
    try:
        query_filter = build_retrieval_filter(
            role=role,
            org_id=org_id,
            org_ids=org_ids,
            subscribed_org_ids=subscribed_org_ids,
        )
        if query_filter is None:
            logger.warning("No valid retrieval scope for role=%s", role)
            return []

        results = qdrant.client.query_points(
            collection_name=qdrant.COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )

        chunks: List[Dict] = []
        for hit in results.points:
            if hit.score >= score_threshold:
                payload = hit.payload or {}
                chunks.append(
                    {
                        "document_id": payload.get("document_id"),
                        "chunk_index": payload.get("chunk_index"),
                        "text": payload.get("chunk_text", ""),
                        "source_name": payload.get("source_name", "unknown"),
                        "score": hit.score,
                    }
                )

        scope = org_id or org_ids or subscribed_org_ids
        logger.info("Retrieved %d chunks (role=%s, scope=%s)", len(chunks), role, scope)
        return chunks
    except Exception as exc:
        logger.error("Error retrieving chunks from Qdrant: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Step 2 — Build a token-budget-aware prompt
# ---------------------------------------------------------------------------
def build_prompt(question: str, chunks: List[Dict], token_budget: int = 2000) -> tuple:
    """Assemble a RAG prompt from retrieved chunks, respecting a token budget.

    Returns (prompt_text, used_chunks).
    """
    if not chunks:
        prompt_text = (
            "You are a helpful assistant for an organization's knowledge base.\n"
            "The user is asking a question, but NO relevant documents or specific context was found in the database (embeddings were not found).\n"
            "You MUST start your response by explicitly informing the user that no relevant documents or specific context were found in the knowledge base, "
            "and then you may try to answer their question using your general knowledge, or greet them if they are just saying hello.\n\n"
            f"User message: {question}\n\n"
            "Response:"
        )
        no_context_source = {
            "document_id": "none",
            "chunk_index": 0,
            "source_name": "No relevant documents found",
            "excerpt": "No semantic matches or context found in the database.",
            "score": 0.0,
        }
        return prompt_text, [no_context_source]

    header = (
        "You are a helpful assistant for an organization's knowledge base.\n"
        "Answer the following question. Use the provided context to answer the question as accurately and concisely as possible. "
        "Cite the sources as [1], [2], etc. where appropriate. "
        "If the provided context does not contain the answer, you may answer the question using your general knowledge, "
        "but clearly state that the information was not found in the organization's documents.\n\n"
        f"Question: {question}\n\n"
        "Context:\n"
    )

    used_chunks: List[Dict] = []
    body = ""
    estimated_tokens = len(header.split())

    for idx, chunk in enumerate(chunks, start=1):
        snippet = chunk["text"][:500]  # cap per-chunk length
        block = f"\n[{idx}] Source: {chunk['source_name']} (chunk {chunk['chunk_index']}):\n{snippet}\n"
        block_tokens = len(block.split())

        if estimated_tokens + block_tokens > token_budget:
            break

        body += block
        estimated_tokens += block_tokens
        used_chunks.append(
            {
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "source_name": chunk["source_name"],
                "excerpt": chunk["text"][:200],
                "score": round(chunk["score"], 4),
            }
        )

    footer = "\nAnswer (reference sources as [1], [2], etc.):\n"
    prompt_text = header + body + footer
    return prompt_text, used_chunks


# ---------------------------------------------------------------------------
# Step 3 — Call Groq LLM
# ---------------------------------------------------------------------------
async def generate_answer(prompt: str, model: str = DEFAULT_LLM_MODEL) -> tuple:
    """Send the prompt to Groq and return (answer_text, response_time_ms).

    Uses the correct Groq Python SDK interface:
        groq_client.chat.completions.create(...)
        response.choices[0].message.content
    """
    try:
        t0 = time.time()
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        answer = response.choices[0].message.content or ""
        logger.info("LLM answer generated in %d ms (model=%s)", elapsed_ms, model)
        return answer, elapsed_ms
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        return "Error generating a response. Please try again.", 0


# ---------------------------------------------------------------------------
# Step 4 — Persist query log to MongoDB
# ---------------------------------------------------------------------------
async def log_query(
    organization_id: str,
    user_id: str,
    question: str,
    answer: str,
    category: str,
    sources: List[Dict],
    response_time_ms: int,
    conversation_id: str,
) -> Optional[str]:
    """Write the completed query to MongoDB `queries` collection."""
    try:
        doc = {
            "organization_id": organization_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "question": question,
            "answer": answer,
            "category": category,
            "sources": sources,
            "chunks_retrieved": len(sources),
            "response_time_ms": response_time_ms,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        result = await mongodb.db.queries.insert_one(doc)
        query_id = str(result.inserted_id)
        logger.info("Query logged: id=%s org=%s convo=%s", query_id, organization_id, conversation_id)
        return query_id
    except Exception as exc:
        logger.error("Failed to log query: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def handle_query(
    question: str,
    user_id: str,
    embedding_model,
    role: str = "org_member",
    org_id: Optional[str] = None,
    org_ids: Optional[List[str]] = None,
    subscribed_org_ids: Optional[List[str]] = None,
    classifier=None,
    top_k: int = 8,
    conversation_id: Optional[str] = None,
) -> Dict:
    """
    Full RAG pipeline:
      1. Embed the question
      2. Retrieve relevant chunks from Qdrant (org-scoped)
      3. Classify the query category
      4. Build a context-aware prompt
      5. Generate an answer via Groq LLM
      6. Log the query to MongoDB
      7. Return structured result
    """
    t0 = time.time()
    
    # Generate conversation ID if not provided
    convo_id = conversation_id or f"convo_{str(ObjectId())}"

    try:
        # 1. Embed the question
        query_vector: List[float] = embedding_model.encode([question])[0].tolist()

        # 2. Retrieve chunks (role-aware)
        chunks = await retrieve_chunks(
            query_vector,
            role=role,
            org_id=org_id,
            org_ids=org_ids,
            subscribed_org_ids=subscribed_org_ids,
            top_k=top_k,
        )

        log_org_id = org_id or (org_ids[0] if org_ids else None)

        # 3. Classify
        category = "general"
        if classifier:
            try:
                category = classifier.predict([question])[0]
            except Exception as exc:
                logger.warning("Classification failed (using 'general'): %s", exc)

        # 4. Build prompt
        prompt, used_chunks = build_prompt(question, chunks)

        # 5. Generate answer
        answer, _llm_ms = await generate_answer(prompt)

        # 6. Log to MongoDB
        total_ms = int((time.time() - t0) * 1000)
        await log_query(
            organization_id=log_org_id or "",
            user_id=user_id,
            question=question,
            answer=answer,
            category=category,
            sources=used_chunks,
            response_time_ms=total_ms,
            conversation_id=convo_id,
        )

        # 7. Confidence = mean similarity score of top-3 retrieved chunks
        top_scores = [c["score"] for c in chunks[:3]]
        confidence = round(sum(top_scores) / len(top_scores), 4) if top_scores else 0.0

        return {
            "answer": answer,
            "sources": used_chunks,
            "category": category,
            "confidence": confidence,
            "response_time_ms": total_ms,
            "conversation_id": convo_id,
        }

    except Exception as exc:
        logger.exception("Unexpected error in RAG pipeline")
        total_ms = int((time.time() - t0) * 1000)
        return {
            "answer": "An internal error occurred while processing your question. Please try again.",
            "sources": [],
            "category": "error",
            "confidence": 0.0,
            "response_time_ms": total_ms,
            "conversation_id": convo_id,
        }
