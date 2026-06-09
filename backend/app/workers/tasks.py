import logging
import time
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal
from app.agents.graph_builder import ingestion_graph
from app.agents.state import FoundryState

logger = logging.getLogger(__name__)

async def process_document_job(job_id: str, document_id: str, facility_id: str, doc_type: str):
    """Run the ingestion graph for a given job and update database state."""
    logger.info(f"Starting process_document_job for {job_id}")
    
    initial_state: FoundryState = {
        "job_id": job_id,
        "document_id": document_id,
        "facility_id": facility_id,
        "input_type": "document",
        "doc_type": doc_type,
        "raw_text": "",
        "extracted_entities": [],
        "observations": [],
        "pending_actions": [],
        "risk_events": [],
        "error": None,
        "status": "processing",
        "current_stage": "started"
    }

    try:
        async with AsyncSessionLocal() as db:
            # Mark job as processing
            await db.execute(
                text("UPDATE ingestion_jobs SET status = 'processing', started_at = now(), stage_log = CAST('[]' AS jsonb) WHERE id = :id"),
                {"id": job_id}
            )
            await db.commit()

        # Stream graph updates
        start_time = time.time()
        
        # We need to use aio stream if graph is async, but we can also just use ainvoke
        # Actually LangGraph async streams are available as astream
        async for output in ingestion_graph.astream(initial_state):
            # Output is a dict mapping node_name to its return value
            for node_name, state_update in output.items():
                logger.info(f"Graph node {node_name} completed.")
                
                # Update job in db
                stage_name = state_update.get("current_stage", node_name)
                duration_ms = int((time.time() - start_time) * 1000)
                start_time = time.time()
                
                stage_status = state_update.get("status", "completed")
                if state_update.get("error"):
                    stage_status = "error"
                
                async with AsyncSessionLocal() as db:
                    # Append to stage_log
                    log_entry = f'{{"stage": "{stage_name}", "status": "{stage_status}", "duration_ms": {duration_ms}}}'
                    await db.execute(
                        text("""
                            UPDATE ingestion_jobs 
                            SET stage_log = stage_log || CAST(:log_entry AS jsonb)
                            WHERE id = :id
                        """),
                        {"id": job_id, "log_entry": log_entry}
                    )
                    await db.commit()

                if stage_status == "error":
                    raise Exception(state_update.get("error", "Unknown error in graph"))

        # Mark job and document as complete
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE ingestion_jobs SET status = 'completed', ended_at = now() WHERE id = :id"),
                {"id": job_id}
            )
            await db.execute(
                text("UPDATE documents SET status = 'completed', processed_at = now() WHERE id = :id"),
                {"id": document_id}
            )
            await db.commit()
            
        logger.info(f"Finished process_document_job for {job_id}")

    except Exception as e:
        logger.error(f"Error in process_document_job {job_id}: {e}")
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE ingestion_jobs SET status = 'failed', ended_at = now(), error_msg = :err WHERE id = :id"),
                {"id": job_id, "err": str(e)}
            )
            await db.execute(
                text("UPDATE documents SET status = 'failed', error_msg = :err WHERE id = :id"),
                {"id": document_id, "err": str(e)}
            )
            await db.commit()
