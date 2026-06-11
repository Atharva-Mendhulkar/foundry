import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.neo4j import neo4j_db
from app.db.lancedb import init_lancedb
from app.routers import auth, ingest, graph, copilot
import httpx
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    neo4j_db.connect()
    init_lancedb()
    
    # Warmup Ollama (optional, background)
    async def warmup():
        try:
            async with httpx.AsyncClient() as client:
                await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        except Exception:
            pass
    asyncio.create_task(warmup())
    
    yield
    
    # Shutdown
    await neo4j_db.close()

app = FastAPI(title="Foundry API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(ingest.router)
app.include_router(ingest.ws_router)
app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(copilot.router, prefix="/api/v1/copilot", tags=["copilot"])

@app.get("/api/v1/health")
async def health_check():
    # Simple health check as requested by Phase 0 DOD
    return {"status": "ok"}
