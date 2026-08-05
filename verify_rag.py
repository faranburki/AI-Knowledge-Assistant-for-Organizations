import asyncio
import os
import sys

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sentence_transformers import SentenceTransformer
from Backend.Database.chroma import connect_to_chroma
from Backend.Database.mongodb import connect_to_mongo
from Backend.Services.embedding_service import save_embeddings_to_chroma
from Backend.Services.rag_pipeline import retrieve_chunks, build_prompt, generate_answer

async def verify():
    # 1. Initialize databases
    print("Connecting to MongoDB and ChromaDB...")
    await connect_to_mongo()
    await connect_to_chroma()
    
    # 2. Load model
    print("Loading embedding model...")
    model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    # 3. Add test data
    print("Injecting test data...")
    test_text = "The new marketing campaign for the organization is called 'Project Xylophone' and officially launches on January 15, 2026."
    test_metadata = {
        "document_id": "test_doc_001",
        "organization_id": "org_test",
        "source_name": "campaign_info.txt",
        "file_type": "txt",
        "upload_user_id": "user_1",
        "status": "private",
    }
    

    await save_embeddings_to_chroma(
        chunks=[test_text],
        metadata=test_metadata,
        model=model
    )
    
    # 4. Retrieve data
    question = "What is the new marketing campaign called and when does it launch?"
    print(f"\nQuerying: {question}")
    
    # By normalizing embeddings to unit vectors, we force ChromaDB to calculate exact Cosine Similarity
    query_vector = model.encode([question], normalize_embeddings=True)[0].tolist()
    
    chunks = await retrieve_chunks(
        query_vector=query_vector,
        role="org_member",
        org_id="org_test",
        top_k=3
    )
    
    print("\nRetrieved Chunks:")
    for c in chunks:
        print(f" - Score: {c['score']:.4f} | Text: {c['text']}")
        
    if not chunks:
        print("ERROR: No chunks retrieved!")
        return
        
    # 5. Generate Answer
    prompt, used_chunks = build_prompt(question, chunks)
    print("\nGenerating answer with local Ollama model...")
    answer, _ = await generate_answer(prompt)
    
    print("\n" + "="*50)
    print("FINAL ANSWER FROM LLM:")
    print(answer)
    print("="*50)
    
    # Clean up
    from Backend.Database import chroma
    chroma.collection.delete(where={"document_id": "test_doc_001"})
    print("\nCleaned up test data.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(verify())
