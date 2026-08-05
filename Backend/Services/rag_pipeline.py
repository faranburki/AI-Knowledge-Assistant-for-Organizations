import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import asyncio
import httpx

from Backend.Database.mongodb import mongodb
from Backend.Database import chroma
from bson import ObjectId

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local Ollama LLM configuration
# ---------------------------------------------------------------------------
DEFAULT_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2:1.5b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# ---------------------------------------------------------------------------
# Step 1 — Retrieve relevant chunks from Qdrant
# ---------------------------------------------------------------------------
def build_retrieval_filter(
    role: str,
    org_id: Optional[str] = None,
    org_ids: Optional[List[str]] = None,
    subscribed_org_ids: Optional[List[str]] = None,
):
    """Build a ChromaDB filter based on the querying user's role."""

    if role == "public_user":
        target_orgs = org_ids if org_ids else (subscribed_org_ids or [])
        if not target_orgs:
            return None
        return {
            "$and": [
                {"organization_id": {"$in": target_orgs}},
                {"status": {"$eq": "public"}},
            ]
        }

    if not org_id:
        return None

    return {
        "organization_id": {"$eq": org_id}
    }


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

        def _query():
            return chroma.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=query_filter,
                include=["metadatas", "documents", "distances"]
            )
            
        results = await asyncio.to_thread(_query)

        chunks: List[Dict] = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
                score = 1.0 - distance  # Convert cosine distance to cosine similarity
                if score >= score_threshold:
                    payload = results["metadatas"][0][i] or {}
                    chunk_text = results["documents"][0][i] or ""
                    chunks.append(
                        {
                            "document_id": payload.get("document_id"),
                            "chunk_index": payload.get("chunk_index"),
                            "text": chunk_text,
                            "source_name": payload.get("source_name", "unknown"),
                            "score": score,
                        }
                    )

        scope = org_id or org_ids or subscribed_org_ids
        logger.info("Retrieved %d chunks (role=%s, scope=%s)", len(chunks), role, scope)
        return chunks
    except Exception as exc:
        logger.error("Error retrieving chunks from ChromaDB: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Step 2 — Build a token-budget-aware prompt
# ---------------------------------------------------------------------------
def build_prompt(question: str, chunks: List[Dict], token_budget: int = 800) -> tuple:
    """Assemble a RAG prompt from retrieved chunks, respecting a tighter token budget.

    Returns (prompt_text, used_chunks).
    """
    if not chunks:
        prompt_text = (
            "You are an expert AI Knowledge Agent for the organization. "
            "The user is asking a question, but NO relevant documents were found.\n"
            "You MUST state that the information was not found in the documents.\n\n"
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
        "You are an expert AI Knowledge Agent. "
        "Answer the user's question concisely in 1-2 sentences using ONLY the provided context below. "
        "Do not hallucinate or add extra information. If the context does not contain the answer, clearly state 'I cannot find the answer in the provided documents.'\n\n"
        "Context:\n"
    )

    used_chunks: List[Dict] = []
    prompt_text = header
    estimated_tokens = len(header.split())

    for idx, chunk in enumerate(chunks, start=1):
        snippet = chunk["text"]  # DO NOT truncate characters; token_budget handles limits
        block = f"\n[{idx}] Source: {chunk['source_name']} (chunk {chunk['chunk_index']}):\n{snippet}\n"
        block_tokens = len(block.split())

        if estimated_tokens + block_tokens > token_budget:
            break

        prompt_text += block
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

    prompt_text += f"\nQuestion: {question}\nAnswer:"
    return prompt_text, used_chunks


# ---------------------------------------------------------------------------
# Step 3 — Call Groq LLM
# ---------------------------------------------------------------------------
async def generate_answer(prompt: str, model: str = DEFAULT_LLM_MODEL) -> tuple:
    """Send the prompt to local Ollama and return (answer_text, response_time_ms)."""
    try:
        t0 = time.time()
        async with httpx.AsyncClient() as client:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 250,
                    "stop": ["\n\nQuestion:", "User:", "Question:"]
                }
            }
            response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120.0)
            response.raise_for_status()
            data = response.json()
            answer = data.get("message", {}).get("content", "")
            
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info("LLM answer generated in %d ms (model=%s)", elapsed_ms, model)
        return answer, elapsed_ms
    except Exception as exc:
        logger.error("Ollama API call failed: %s", exc)
        return "Error generating a response from the local model. Please try again.", 0


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
        log_org_id = org_id or (org_ids[0] if org_ids else "")
        
        # 0. Check Cache
        if log_org_id:
            cached_query = await mongodb.db.queries.find_one(
                {"organization_id": log_org_id, "question": question, "category": {"$ne": "error"}},
                sort=[("timestamp", -1)]
            )
            if cached_query and cached_query.get("answer"):
                # We return cache if it's not a generic failure response
                ans = cached_query["answer"]
                if "An internal error occurred" not in ans:
                    logger.info("Cache hit for question: '%s'", question)
                    
                    # Log this specific turn to the conversation history
                    query_doc = {
                        "organization_id": log_org_id,
                        "user_id": user_id,
                        "conversation_id": convo_id,
                        "question": question,
                        "answer": ans,
                        "category": cached_query.get("category", "general"),
                        "sources": cached_query.get("sources", []),
                        "confidence": 0.99,
                        "response_time_ms": int((time.time() - t0) * 1000),
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    await mongodb.db.queries.insert_one(query_doc)
                    
                    return {
                        "answer": ans,
                        "sources": cached_query.get("sources", []),
                        "category": cached_query.get("category", "general"),
                        "confidence": 0.99,
                        "response_time_ms": int((time.time() - t0) * 1000),
                        "conversation_id": convo_id,
                    }

        # 1. Embed the question asynchronously (Normalized)
        def _encode():
            return embedding_model.encode([question], normalize_embeddings=True)[0].tolist()
            
        query_vector: List[float] = await asyncio.to_thread(_encode)

        # 2. Retrieve chunks (role-aware)
        chunks = await retrieve_chunks(
            query_vector,
            role=role,
            org_id=org_id,
            org_ids=org_ids,
            subscribed_org_ids=subscribed_org_ids,
            top_k=3,  # Cap at 3 to aggressively improve CPU response times
        )

        # 3. Classify
        category = "general"
        if classifier:
            try:
                category = classifier.predict([question])[0]
            except Exception as exc:
                logger.warning("Classification failed (using 'general'): %s", exc)

        # 4. Build prompt
        prompt, used_chunks = build_prompt(question, chunks)
        
        # Deduplicate sources for the frontend by source_name
        unique_sources = []
        seen_sources = set()
        for src in used_chunks:
            if src["source_name"] not in seen_sources:
                unique_sources.append(src)
                seen_sources.add(src["source_name"])

        # 5. Log to MongoDB IMMEDIATELY so frontend shows the transcription
        query_doc = {
            "organization_id": log_org_id or "",
            "user_id": user_id,
            "conversation_id": convo_id,
            "question": question,
            "answer": "Thinking...",
            "category": category,
            "sources": unique_sources,
            "confidence": 0.0,
            "response_time_ms": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        insert_result = await mongodb.db.queries.insert_one(query_doc)
        query_id = insert_result.inserted_id

        # 6. Generate answer
        answer, _llm_ms = await generate_answer(prompt)

        # 7. Update MongoDB with real answer
        total_ms = int((time.time() - t0) * 1000)
        
        top_scores = [c["score"] for c in chunks[:3]]
        confidence = round(sum(top_scores) / len(top_scores), 4) if top_scores else 0.0

        await mongodb.db.queries.update_one(
            {"_id": query_id},
            {"$set": {
                "answer": answer,
                "confidence": confidence,
                "response_time_ms": total_ms
            }}
        )

        return {
            "answer": answer,
            "sources": unique_sources,
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
