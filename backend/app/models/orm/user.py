from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.postgres import Base

class Facility(Base):
    __tablename__ = "facilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(200), nullable=False)
    type = Column(String(50))
    timezone = Column(String(50), nullable=False, server_default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(30), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="RESTRICT"))
    is_active = Column(Boolean, server_default="true")
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
