"""initial

Revision ID: 001_initial
Revises: 
Create Date: 2024-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # facilities
    op.create_table('facilities',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('timezone', sa.String(length=50), server_default='UTC', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # users
    op.create_table('users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('facility_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    # documents
    op.create_table('documents',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False),
        sa.Column('facility_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.String(length=500), nullable=True),
        sa.Column('uploaded_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_hash')
    )
    op.create_index('idx_documents_facility', 'documents', ['facility_id'], unique=False)
    op.create_index('idx_documents_status', 'documents', ['status'], unique=False)
    op.create_index('idx_documents_hash', 'documents', ['file_hash'], unique=False)

    # ingestion_jobs
    op.create_table('ingestion_jobs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='queued', nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('stage_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # shifts
    op.create_table('shifts',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('facility_id', sa.UUID(), nullable=True),
        sa.Column('shift_type', sa.String(length=20), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_notes', sa.Text(), nullable=True),
        sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('pending_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('neo4j_shift_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_shifts_facility', 'shifts', ['facility_id'], unique=False)
    op.create_index('idx_shifts_start_time', 'shifts', [sa.text('start_time DESC')], unique=False)

    # risk_snapshots
    op.create_table('risk_snapshots',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('facility_id', sa.UUID(), nullable=True),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('heatmap_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('top_risks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('window_days', sa.Integer(), server_default='30', nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_risk_snapshots_facility', 'risk_snapshots', ['facility_id', sa.text('snapshot_time DESC')], unique=False)

    # copilot_sessions
    op.create_table('copilot_sessions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('facility_id', sa.UUID(), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.SmallInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sessions_user', 'copilot_sessions', ['user_id'], unique=False)

    # audit_logs
    op.create_table('audit_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.String(length=200), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'], unique=False)
    op.create_index('idx_audit_time', 'audit_logs', [sa.text('created_at DESC')], unique=False)

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('copilot_sessions')
    op.drop_table('risk_snapshots')
    op.drop_table('shifts')
    op.drop_table('ingestion_jobs')
    op.drop_table('documents')
    op.drop_table('users')
    op.drop_table('facilities')
