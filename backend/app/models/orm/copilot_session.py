from sqlalchemy import Column, String, SmallInteger, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.postgres import Base

class CopilotSession(Base):
    __tablename__ = "copilot_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    query = Column(Text, nullable=False)
    response = Column(Text)
    sources = Column(JSONB)
    latency_ms = Column(Integer)
    feedback = Column(SmallInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(200))
    details = Column(JSONB)
    # inet column representation in sqlalchemy string is fine for schema, but we'll use a string for simplicity in python side if we don't need inet specifics
    ip_address = Column(String(50)) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
