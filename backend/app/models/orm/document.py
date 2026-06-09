from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.postgres import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    filename = Column(String(500), nullable=False)
    doc_type = Column(String(50), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    status = Column(String(30), server_default="pending")
    file_hash = Column(String(64), unique=True)
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    storage_path = Column(String(500))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    error_msg = Column(Text)

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    worker_id = Column(String(100))
    status = Column(String(30), server_default="queued")
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    error_msg = Column(Text)
    stage_log = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
