from app.services.llm_service import ollama_client
from app.db.lancedb import get_lancedb_connection
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
from typing import List, Dict, Any
import time

logger = logging.getLogger(__name__)

async def embed_chunks(text: str, document_id: str, doc_type: str, facility_id: str) -> List[Dict[str, Any]]:
    """Chunk text, generate embeddings, and save to LanceDB."""
    try:
        # 1. Chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            length_function=len,
        )
        chunks = text_splitter.split_text(text)
        
        if not chunks:
            logger.warning(f"No chunks generated for document {document_id}")
            return []

        logger.info(f"Generated {len(chunks)} chunks for document {document_id}")
        
        # 2. Embedding
        db_records = []
        # Process sequentially to avoid overwhelming local Ollama
        for i, chunk in enumerate(chunks):
            embedding = await ollama_client.embed(chunk, model="nomic-embed-text")
            
            # 3. Prepare records
            record = {
                "id": f"{document_id}_{i}",
                "doc_id": document_id,
                "chunk_index": i,
                "text": chunk,
                "embedding": embedding,
                "doc_type": doc_type,
                "facility_id": facility_id,
                "entity_ids": [],  # Will be populated in Phase 2
                "created_at": int(time.time() * 1000)
            }
            db_records.append(record)
            
        # 4. Save to LanceDB
        if db_records:
            db = get_lancedb_connection()
            table = db.open_table("documents")
            table.add(db_records)
            logger.info(f"Saved {len(db_records)} records to LanceDB")
            
        return db_records
        
    except Exception as e:
        logger.error(f"Error in embed_chunks: {e}")
        raise e
