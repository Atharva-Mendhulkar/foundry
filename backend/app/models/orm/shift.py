from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.postgres import Base

class Shift(Base):
    __tablename__ = "shifts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    shift_type = Column(String(20))
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    raw_notes = Column(Text)
    structured_data = Column(JSONB)
    summary_text = Column(Text)
    risk_level = Column(String(20))
    pending_actions = Column(JSONB)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    neo4j_shift_id = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    snapshot_time = Column(DateTime(timezone=True), server_default=func.now())
    heatmap_data = Column(JSONB, nullable=False)
    top_risks = Column(JSONB)
    window_days = Column(Integer, server_default="30")
