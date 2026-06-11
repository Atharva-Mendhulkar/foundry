from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal
from app.workers.tasks import process_document_job
from app.core.deps import get_current_user
from typing import Any
import os
import hashlib
import uuid
import json
import asyncio
import csv
from io import StringIO
from app.services.graph_service import GraphService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])
ws_router = APIRouter()

UPLOAD_DIR = "/tmp/foundry_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/document")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form("sop"),
    current_user: Any = Depends(get_current_user)
):
    """Upload a document for ingestion."""
    # 1. Save file and compute hash
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # 2. Check for duplicate
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT id, status FROM documents WHERE file_hash = :hash"),
            {"hash": file_hash}
        )
        existing = result.first()
        if existing:
            # Document exists
            doc_id = existing[0]
            # Get associated job
            job_res = await db.execute(
                text("SELECT id FROM ingestion_jobs WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"),
                {"doc_id": doc_id}
            )
            job = job_res.first()
            if job:
                raise HTTPException(status_code=409, detail={"message": "Document already exists", "job_id": str(job[0]), "document_id": str(doc_id)})

    # Save to disk
    file_path = os.path.join(UPLOAD_DIR, f"{file_hash}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)
        
    facility_id = current_user.facility_id

    # 3. Create document record
    async with AsyncSessionLocal() as db:
        doc_res = await db.execute(
            text("""
                INSERT INTO documents (filename, doc_type, facility_id, file_hash, file_size, mime_type, storage_path, uploaded_by)
                VALUES (:filename, :doc_type, :facility, :hash, :size, :mime, :path, :user_id)
                RETURNING id
            """),
            {
                "filename": file.filename,
                "doc_type": doc_type,
                "facility": facility_id,
                "hash": file_hash,
                "size": len(content),
                "mime": file.content_type,
                "path": file_path,
                "user_id": current_user.id
            }
        )
        document_id = str(doc_res.first()[0])
        
        # 4. Create job record
        job_res = await db.execute(
            text("""
                INSERT INTO ingestion_jobs (document_id, status)
                VALUES (:doc_id, 'queued')
                RETURNING id
            """),
            {"doc_id": document_id}
        )
        job_id = str(job_res.first()[0])
        await db.commit()
        
    # 5. Queue background task
    background_tasks.add_task(process_document_job, job_id, document_id, str(facility_id), doc_type)
    
    return {"job_id": job_id, "document_id": document_id, "status": "queued"}

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the current status of an ingestion job."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT status, stage_log, error_msg FROM ingestion_jobs WHERE id = :id"),
            {"id": job_id}
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
            
        return {
            "status": row[0],
            "stages": row[1] if row[1] else [],
            "error": row[2]
        }

@router.get("/documents")
async def list_documents(page: int = 1, per_page: int = 20, current_user: Any = Depends(get_current_user)):
    """List uploaded documents."""
    offset = (page - 1) * per_page
    facility_id = current_user.facility_id
    
    async with AsyncSessionLocal() as db:
        total_res = await db.execute(text("SELECT count(*) FROM documents WHERE facility_id = :fid"), {"fid": facility_id})
        total = total_res.first()[0]
        
        docs_res = await db.execute(
            text("""
                SELECT id, filename, doc_type, status, created_at 
                FROM documents 
                WHERE facility_id = :fid 
                ORDER BY created_at DESC 
                LIMIT :limit OFFSET :offset
            """),
            {"fid": facility_id, "limit": per_page, "offset": offset}
        )
        
        items = []
        for row in docs_res:
            items.append({
                "id": str(row[0]),
                "filename": row[1],
                "doc_type": row[2],
                "status": row[3],
                "created_at": row[4].isoformat()
            })
            
        return {"items": items, "total": total}

@router.post("/workorders-csv")
async def upload_workorders_csv(
    file: UploadFile = File(...),
    current_user: Any = Depends(get_current_user)
):
    """Bulk import work orders from CSV directly into the Knowledge Graph."""
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
        csv_reader = csv.DictReader(StringIO(text_content))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid CSV format")
        
    rows_queued = 0
    facility_id = current_user.facility_id
    
    for row in csv_reader:
        wo_number = row.get("wo_number")
        eq_name = row.get("equipment_name")
        failure_mode = row.get("failure_mode")
        proc_code = row.get("procedure_code")
        
        if not wo_number or not eq_name:
            continue
            
        try:
            # 1. Upsert Equipment
            eq = {"name": eq_name, "type": "unknown", "status": "operational"}
            eq_id = await GraphService.upsert_equipment(eq, str(facility_id))
            
            # 2. Upsert Failure
            if failure_mode:
                fail = {"description": f"Work Order {wo_number}", "failure_mode": failure_mode}
                f_id = await GraphService.upsert_failure(fail, eq_id)
                
                # 3. Upsert Procedure
                if proc_code:
                    proc = {"code": proc_code, "title": f"Procedure {proc_code}"}
                    p_id = await GraphService.upsert_procedure(proc)
                    await GraphService.link_failure_to_procedure(f_id, p_id)
            
            # For hackathon MVP we write directly instead of using LangGraph background job
            rows_queued += 1
        except Exception as e:
            logger.error(f"Error processing CSV row {wo_number}: {e}")
            
    # Mocking job_id since we process synchronously for demo simplicity
    return {"job_id": str(uuid.uuid4()), "rows_queued": rows_queued}

# WebSocket route must be separate to mount at /ws
@ws_router.websocket("/ws/ingest/{job_id}")
async def ingest_websocket(websocket: WebSocket, job_id: str):
    """Stream job progress via WebSocket."""
    await websocket.accept()
    
    try:
        last_log_len = 0
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT status, stage_log, error_msg FROM ingestion_jobs WHERE id = :id"),
                    {"id": job_id}
                )
                row = result.first()
                
            if not row:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                break
                
            status, stage_log, error_msg = row
            stage_log = stage_log or []
            
            # Send any new stages
            if len(stage_log) > last_log_len:
                for stage in stage_log[last_log_len:]:
                    await websocket.send_json({
                        "type": "progress",
                        "stage": stage.get("stage"),
                        "status": stage.get("status")
                    })
                last_log_len = len(stage_log)
                
            if status == "completed":
                await websocket.send_json({"type": "complete"})
                break
            elif status == "failed":
                await websocket.send_json({"type": "error", "message": error_msg})
                break
                
            await asyncio.sleep(1) # Poll interval
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
