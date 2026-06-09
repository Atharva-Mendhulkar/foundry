import lancedb
import pyarrow as pa
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# LanceDB Schema
document_schema = pa.schema([
    pa.field("id",           pa.string()),
    pa.field("doc_id",       pa.string()),
    pa.field("chunk_index",  pa.int32()),
    pa.field("text",         pa.string()),
    pa.field("embedding",    pa.list_(pa.float32(), 768)),  # nomic-embed-text dim
    pa.field("doc_type",     pa.string()),   # sop, work_order, shift_note
    pa.field("facility_id",  pa.string()),
    pa.field("entity_ids",   pa.list_(pa.string())),  # linked Neo4j IDs
    pa.field("created_at",   pa.timestamp("ms")),
])

def get_lancedb_connection():
    return lancedb.connect(settings.LANCEDB_URI)

def init_lancedb():
    db = get_lancedb_connection()
    if "documents" not in db.table_names():
        logger.info("Creating LanceDB 'documents' table")
        db.create_table("documents", schema=document_schema)
        logger.info("Created 'documents' table successfully")
    else:
        logger.info("LanceDB 'documents' table already exists")
