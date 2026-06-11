import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.deps import get_current_user
from app.agents.graph_builder import ingestion_graph
from app.services.llm_service import ollama_client

logger = logging.getLogger(__name__)

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    equipment_context: Optional[str] = None

class QueryResponse(BaseModel):
    session_id: str
    response: str
    sources: List[Dict[str, Any]]
    latency_ms: int
    confidence: str

@router.post("/query", response_model=QueryResponse)
async def copilot_query(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """Non-streaming copilot query."""
    try:
        # Run graph for retrieval
        initial_state = {
            "job_id": "sync-query",
            "document_id": "sync-query",
            "facility_id": current_user.get("facility_id", "nexus-01"),
            "input_type": "query",
            "doc_type": "query",
            "raw_text": "",
            "extracted_entities": [],
            "observations": [],
            "pending_actions": [],
            "risk_events": [],
            "query": request.query,
            "session_id": request.session_id,
            "user_id": str(current_user.get("id")),
            "equipment_context": request.equipment_context,
            "status": "processing",
            "current_stage": "init",
            "error": None
        }
        
        final_state = await ingestion_graph.ainvoke(initial_state)
        if final_state.get("error"):
            raise HTTPException(status_code=500, detail=final_state["error"])
            
        merged_context = final_state.get("merged_context", "")
        vector_results = final_state.get("vector_results", [])
        
        system_prompt = f"""You are an industrial engineering assistant. 
Use ONLY the provided context to answer the user's query. 
Cite sources as [DOC-ID]. If context is insufficient, say exactly that.

CONTEXT:
{merged_context}"""
        
        response = await ollama_client.generate(prompt=request.query, system=system_prompt)
        
        return QueryResponse(
            session_id=request.session_id or "new-session",
            response=response,
            sources=vector_results,
            latency_ms=0,
            confidence="high"
        )
    except Exception as e:
        logger.error(f"Error in copilot query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected for copilot.")
    
    try:
        data = await websocket.receive_text()
        req = json.loads(data)
        query = req.get("query", "")
        session_id = req.get("session_id", "new-session")
        
        if not query:
            await websocket.send_json({"type": "error", "message": "Missing query"})
            await websocket.close()
            return
            
        initial_state = {
            "job_id": "ws-query",
            "document_id": "ws-query",
            "facility_id": "nexus-01",
            "input_type": "query",
            "doc_type": "query",
            "raw_text": "",
            "extracted_entities": [],
            "observations": [],
            "pending_actions": [],
            "risk_events": [],
            "query": query,
            "session_id": session_id,
            "user_id": "unknown", # WS auth is tricky, bypassing for hackathon demo
            "status": "processing",
            "current_stage": "init",
            "error": None
        }
        
        # We need to run graph async
        final_state = await ingestion_graph.ainvoke(initial_state)
        
        merged_context = final_state.get("merged_context", "")
        vector_results = final_state.get("vector_results", [])
        
        system_prompt = f"""You are an industrial engineering assistant. 
Use ONLY the provided context to answer the user's query. 
Cite sources as [DOC-ID]. If context is insufficient, say exactly that.

CONTEXT:
{merged_context}"""
        
        # Stream from Ollama
        async for token in ollama_client.stream(prompt=query, system=system_prompt):
            await websocket.send_json({"type": "token", "content": token})
            
        await websocket.send_json({"type": "sources", "sources": vector_results})
        await websocket.send_json({"type": "complete", "session_id": session_id, "latency_ms": 1000})
        
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
