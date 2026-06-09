# FOUNDRY — COMPLETE TECHNICAL ARCHITECTURE
## Industrial Memory & Operational Intelligence Platform

**Version:** 1.0 | **Platform:** NVIDIA Jetson AGX Orin 64GB | **Deployment:** Air-gapped Edge  
**Stack:** FastAPI · Neo4j · LanceDB · LangGraph · Qwen3 8B · Next.js · PostgreSQL

---

# SECTION 1: ARCHITECTURE PRINCIPLES

## 1.1 Core Design Philosophy

**Knowledge Persistence Over Ephemeral Retrieval**  
Every ingested artifact permanently updates the Knowledge Graph. The system never discards context — failed retrieval degrades to stale graph data, not a null answer. Relationships between failures, procedures, and equipment must survive across system restarts without re-ingestion.

**Graph-First Data Model**  
Relational databases answer "what happened." Vector databases answer "what is similar." Knowledge graphs answer "why and how are things connected." Foundry's primary intelligence layer is the Neo4j graph — LanceDB exists to surface entry points into the graph, not to replace it.

**Edge-First, Offline-by-Design**  
No feature may require an outbound network call. Inference, storage, and retrieval are colocated on the Jetson. Data backups to external drives are the only permissible egress path. This is not a cloud-first system with offline fallback — it is a genuinely offline system.

**Privacy-by-Architecture**  
The Risk Intelligence Engine operates on `RiskEvent` nodes that carry no Technician identity. The anonymization boundary is enforced at the entity extraction layer, not the API layer. Audit logs exist for access tracking, not performance profiling.

**Asynchronous Ingestion, Synchronous Query**  
Document ingestion is always async (queue-backed). Copilot queries, shift summaries, and risk heatmaps are synchronous with streaming for LLM responses. This prevents ingestion load from degrading query latency.

**Graceful Degradation Stack**  
```
LLM unavailable      → return vector-only search results with graph facts
Neo4j unavailable    → return vector-only results (no graph traversal)
LanceDB unavailable  → return graph-only structured facts
Both unavailable     → return raw PostgreSQL document metadata
```

## 1.2 Architectural Principles

| Principle | Implementation |
|---|---|
| Single source of truth | Neo4j owns the canonical entity registry; Postgres owns operational state |
| Idempotent ingestion | SHA256 document hash deduplication; MERGE semantics in Cypher |
| Bounded LLM dependency | LLM used for extraction and synthesis, not for storage or retrieval logic |
| Schema evolution | Neo4j property additions are non-breaking; Postgres migrations are versioned |
| Deterministic entity IDs | UUIDs derived from `SHA256(type:name:facility_id)` for cross-document resolution |
| Observability | Every LangGraph node emits structured events to a local JSONL trace log |

## 1.3 Tradeoffs Made Explicit

| Decision | Alternative Rejected | Rationale |
|---|---|---|
| Neo4j over ArangoDB | ArangoDB multi-model | Cypher is more expressive for graph traversal; Neo4j's APOC library provides graph algorithms needed for risk pattern detection |
| LanceDB over Chroma | Chroma | LanceDB is a single Python library with no server process — critical for memory-constrained Jetson deployment. Chroma requires a server |
| Qwen3 8B over Llama 3.1 8B | Llama 3.1 8B | Qwen3 8B outperforms Llama 3.1 8B on structured extraction benchmarks; multilingual support matters for global factory deployments; thinking mode available for complex risk analysis |
| ARQ over Celery | Celery | ARQ (async Redis queue) has less overhead; Celery broker + worker complexity not justified at Jetson scale |
| PaddleOCR over Tesseract | Tesseract 5 | PaddleOCR handles multi-column industrial PDFs, rotated text, and dense SOP tables significantly better |
| faster-whisper over NVIDIA Parakeet | Parakeet | Parakeet is English-only; factories deploy globally. Whisper Large V3 via faster-whisper delivers 8x realtime on Jetson GPU with <1.5s latency for 10s audio |
| BAAI/bge-m3 embeddings | text-embedding-ada-002 | No cloud call; 1024-dim; multilingual; runs at 120ms/batch on Jetson |

## 1.4 Scalability Assumptions

This system is designed for **single-facility, single-Jetson** deployment at MVP. Horizontal scaling is explicitly deferred:
- Expected data volume: 50K documents, 500K observations, 2M relationships over 3 years
- Expected concurrent users: 5–20 shift workers + engineers
- Expected query volume: 200 Copilot queries/day, 50 shift summaries/day
- Graph size ceiling: 5M nodes / 20M relationships on Neo4j Community on 2TB NVMe

Multi-facility scaling path: replicate Jetson per facility, sync graph deltas via encrypted USB transfer. Neo4j Enterprise federation is the long-term path but out of MVP scope.

---

# SECTION 2: HIGH-LEVEL ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                                  │
│                    Next.js 14 / React / Tailwind CSS                         │
│   ┌──────────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐ │
│   │ Copilot UI   │ │ Graph Explorer│ │ Risk Heatmap   │ │ Shift Dashboard  │ │
│   └──────────────┘ └──────────────┘ └────────────────┘ └──────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │ REST/WebSocket (localhost:3000 → :8000)
┌─────────────────────────────▼────────────────────────────────────────────────┐
│                        API GATEWAY LAYER                                     │
│              Nginx (TLS termination, rate limiting, static assets)           │
│                    FastAPI (JWT auth, request routing)                       │
└──────┬──────────────┬───────────────┬──────────────┬──────────────┬──────────┘
       │              │               │              │              │
┌──────▼───┐ ┌────────▼──┐ ┌─────────▼─┐ ┌─────────▼──┐ ┌────────▼─────┐
│ Copilot  │ │  Shift    │ │  Risk     │ │  Ingest   │ │    Auth     │
│ Service  │ │  Service  │ │  Service  │ │  Service  │ │   Service   │
└──────┬───┘ └────────┬──┘ └─────────┬─┘ └─────────┬──┘ └─────────────┘
       │              │               │              │
┌──────▼──────────────▼───────────────▼──────────────▼───────────────────────┐
│                         AGENT LAYER  (LangGraph)                            │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │
│  │ Copilot   │ │  Shift   │ │  Risk    │ │Document │ │  Voice          │ │
│  │  Agent    │ │  Agent   │ │  Agent   │ │  Agent  │ │  Agent          │ │
│  └───────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────────────┘ │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │  Entity   │ │  Graph   │ │Retrieval │ │   OCR    │                     │
│  │  Agent    │ │  Agent   │ │  Agent   │ │  Agent   │                     │
│  └───────────┘ └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                        INTELLIGENCE LAYER                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────────┐ │
│  │  Qwen3 8B Q4_KM │  │ BGE-M3 Embed    │  │ BGE Reranker v2-m3         │ │
│  │  (Ollama)       │  │ (faster-embed)  │  │ (cross-encoder)            │ │
│  └─────────────────┘  └─────────────────┘  └────────────────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────────┐ │
│  │ Whisper Large V3│  │ Silero VAD      │  │ PaddleOCR                  │ │
│  │ (faster-whisper)│  │                 │  │                            │ │
│  └─────────────────┘  └─────────────────┘  └────────────────────────────┘ │
└───────────┬────────────────────┬────────────────────┬───────────────────────┘
            │                    │                    │
┌───────────▼────────┐  ┌────────▼──────────┐  ┌─────▼───────────────────────┐
│      Neo4j 5.x     │  │     LanceDB       │  │      PostgreSQL 15          │
│   Knowledge Graph  │  │   Vector Store    │  │    Operational Data        │
│   (2TB NVMe)       │  │   (embedded)      │  │                            │
└────────────────────┘  └───────────────────┘  └─────────────────────────────┘
                                  │
                         ┌────────▼──────────┐
                         │   Redis 7          │
                         │ Task queue + cache │
                         └───────────────────┘
```

## 2.1 Service Boundaries

Each service is a FastAPI router mounted on the main application. Services share process memory but have explicit interface contracts — no service calls another service's internals directly; all cross-service communication goes through the shared agent state or Postgres.

---

# SECTION 3: SYSTEM CONTEXT DIAGRAM

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         FOUNDRY SYSTEM BOUNDARY                             ║
║                      [NVIDIA Jetson AGX Orin 64GB]                          ║
║  ┌───────────────┐          ┌───────────────────────────────────────────┐   ║
║  │  ADMIN        │          │              FOUNDRY PLATFORM              │   ║
║  │  SYSTEMS      │ ◄──────► │  ┌───────────┐    ┌─────────────────────┐ │   ║
║  │               │          │  │ Ingest    │    │  Knowledge Graph    │ │   ║
║  │ • CMMS export │          │  │ Pipeline  │───►│  Neo4j              │ │   ║
║  │ • SAP CSV     │          │  └───────────┘    └─────────────────────┘ │   ║
║  │ • ERP dump    │          │  ┌───────────┐    ┌─────────────────────┐ │   ║
║  └───────────────┘          │  │ LangGraph │    │  Vector Store       │ │   ║
║                             │  │ Agents    │◄──►│  LanceDB            │ │   ║
║  ┌───────────────┐          │  └───────────┘    └─────────────────────┘ │   ║
║  │  DATA SOURCES │          │  ┌───────────┐    ┌─────────────────────┐ │   ║
║  │               │ ──────►  │  │ Qwen3 8B  │    │  Operational DB     │ │   ║
║  │ • SOP PDFs    │          │  │ (Ollama)  │    │  PostgreSQL         │ │   ║
║  │ • Work Orders │          │  └───────────┘    └─────────────────────┘ │   ║
║  │ • Shift notes │          │  ┌───────────┐    ┌─────────────────────┐ │   ║
║  │ • Incident    │          │  │ Whisper   │    │  Task Queue         │ │   ║
║  │   reports     │          │  │ Large V3  │    │  Redis + ARQ        │ │   ║
║  │ • Voice audio │          │  └───────────┘    └─────────────────────┘ │   ║
║  └───────────────┘          └───────────────────────────────────────────┘   ║
║                                          │ REST/WS                          ║
║  ┌───────────────────────────────────────▼─────────────────────────────┐   ║
║  │                         FRONTEND LAYER                               │   ║
║  │   ┌──────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐ │   ║
║  │   │  Technicians │  │  Engineers   │  │ Managers  │  │  Admins  │ │   ║
║  │   │ (Voice, Shift│  │ (Copilot,    │  │ (Heatmap, │  │ (System  │ │   ║
║  │   │  View WOs)   │  │  Graph)      │  │  Reports) │  │  Config) │ │   ║
║  │   └──────────────┘  └──────────────┘  └───────────┘  └──────────┘ │   ║
║  └─────────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════════╝
       │                                                        │
  [Backup]                                                [Laptop/Tablet]
  USB drive                                             WiFi LAN (local)
  encrypted                                               no internet
```

---

# SECTION 4: SERVICE ARCHITECTURE

## 4.1 Ingestion Service

**Responsibilities:** Receive uploaded documents, validate, deduplicate, route to processing queue, track pipeline status.

**Inputs:** Multipart file upload (PDF, DOCX, TXT, CSV, JSON, WAV, OGG, MP3), manual text entry

**Outputs:** `ingestion_job_id`, WebSocket status events, completed document record in Postgres

**APIs:**
```
POST   /api/v1/ingest/document         → {job_id, status}
POST   /api/v1/ingest/voice            → {job_id, status}
POST   /api/v1/ingest/shift-note       → {job_id, status}
GET    /api/v1/ingest/status/{job_id}  → {status, stages, error}
GET    /api/v1/ingest/documents        → paginated list
DELETE /api/v1/ingest/document/{id}    → removes from storage and graph
WS     /ws/ingest/{job_id}             → live status stream
```

**Dependencies:** PostgreSQL (job tracking), Redis (job queue), LangGraph Document Agent

**Failure modes:**
- Duplicate upload → 409 with existing document ID (SHA256 check)
- Corrupt PDF → OCR agent returns empty text → flagged in Postgres, no graph update
- Queue full → 503 with retry-after header
- Storage full → 507 with disk usage metrics

**Deduplication logic:**
```python
file_hash = sha256(file_bytes).hexdigest()
existing = db.query(Document).filter_by(file_hash=file_hash).first()
if existing:
    return {"status": "duplicate", "document_id": existing.id}
```

---

## 4.2 OCR Service

**Responsibilities:** Convert binary documents (PDFs, images, scanned SOPs) to structured text with layout preservation.

**Inputs:** File path to PDF/image on local disk

**Outputs:** Structured text with page markers, table extraction, confidence scores per block

**Implementation:**
```python
from paddleocr import PaddleOCR
import fitz  # PyMuPDF for PDF rasterization

def process_pdf(path: str) -> OCRResult:
    doc = fitz.open(path)
    ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True)
    pages = []
    for page_num, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_array.reshape(pix.height, pix.width, pix.n)
        result = ocr.ocr(img_array, cls=True)
        text_blocks = extract_text_blocks(result)
        pages.append({"page": page_num+1, "blocks": text_blocks})
    return OCRResult(pages=pages, total_chars=sum_chars(pages))
```

**Failure modes:**
- Scanned image too low resolution → retry at 600 DPI
- Non-Latin script → fallback to multilingual PaddleOCR model
- Corrupted PDF → catch fitz exception, return partial result

---

## 4.3 Voice Processing Service

**Responsibilities:** Receive audio files or streaming audio, apply VAD, transcribe with Whisper, return timestamped transcript.

**Inputs:** Audio bytes (WAV 16kHz mono preferred; accepts MP3, OGG via FFmpeg conversion)

**Outputs:** Transcript with word-level timestamps, language detection, confidence

**Implementation stack:**
- Silero VAD v4 → strip silence, split into ≤30s segments
- FFmpeg → normalize to 16kHz mono WAV
- faster-whisper Large V3 (CUDA) → transcribe each segment
- Merge segments → full transcript with timestamps

**Latency table:**
| Audio length | Whisper time (GPU) | Total pipeline |
|---|---|---|
| 10s | 0.9s | 1.4s |
| 30s | 2.1s | 2.8s |
| 60s | 3.8s | 4.6s |
| 180s | 9.5s | 11.2s |

**APIs:**
```
POST /api/v1/voice/transcribe  → {transcript, language, duration_ms, segments}
POST /api/v1/voice/record      → streams chunks, returns job_id
GET  /api/v1/voice/{job_id}    → completed transcript
```

**Failure modes:**
- Industrial background noise → VAD may miss speech segments; solution: configurable VAD threshold per facility
- Non-speech audio → empty transcript, logged as warning
- GPU memory exhaustion → fall back to CPU transcription (3–5× slower but functional)

---

## 4.4 Entity Extraction Service

**Responsibilities:** Parse free text (from OCR, voice transcripts, shift notes) into structured entities using Qwen3 8B via constrained JSON generation.

**Inputs:** Raw text string, document context (type, facility, date)

**Outputs:** Structured JSON entity list with types, names, properties, confidence

**Prompt strategy (few-shot, type-constrained):**
```
SYSTEM: You are an industrial entity extractor. Extract ONLY entities
present in the text. Return ONLY valid JSON. No explanation.

Schema:
{
  "equipment": [{"name": str, "type": str, "location": str|null, "id_hint": str|null}],
  "components": [{"name": str, "part_of": str|null, "part_number": str|null}],
  "failures": [{"description": str, "mode": str, "severity": "low|medium|high|critical"}],
  "procedures": [{"code": str|null, "title": str, "type": "sop|maintenance|emergency"}],
  "work_orders": [{"number": str, "type": str, "priority": str}],
  "observations": [{"content": str, "type": "condition|action|concern|note"}],
  "locations": [{"name": str, "zone": str|null, "area": str|null}]
}

EXAMPLES:
[2 examples of industrial text → expected JSON]

TEXT: {input_text}
```

**Temperature:** 0.0 (deterministic extraction)
**Max tokens:** 1200
**Retry strategy:** If JSON parse fails, re-prompt with error message once; then return partial extraction

---

## 4.5 Knowledge Graph Service

**Responsibilities:** CRUD operations on Neo4j, entity resolution, relationship creation, graph evolution, query execution for retrieval agents.

**Core operations:**
```python
# Entity resolution: deterministic ID generation
def resolve_entity_id(entity_type: str, name: str, facility_id: str) -> str:
    canonical = f"{entity_type}:{name.lower().strip()}:{facility_id}"
    return str(uuid.UUID(bytes=hashlib.sha256(canonical.encode()).digest()[:16]))

# MERGE pattern prevents duplicates
def upsert_equipment(equipment: EquipmentEntity, facility_id: str):
    query = """
    MERGE (e:Equipment {id: $id})
    ON CREATE SET e.name=$name, e.type=$type, e.facility_id=$fid, 
                  e.created_at=datetime()
    ON MATCH SET  e.name=$name, e.type=$type, e.updated_at=datetime()
    RETURN e
    """
```

**Failure modes:**
- Neo4j connection loss → write-behind queue in Redis, replay on reconnect
- Circular relationship detection → graph constraint on causal chains ([:CAUSED*] depth limit 10)
- Schema violation → Cypher constraint catches, entity queued for manual review

---

## 4.6 GraphRAG Service

**Responsibilities:** Implement the hybrid retrieval pipeline combining vector search with graph traversal, merge and rerank results, assemble context for LLM.

*(Full design in Section 7)*

---

## 4.7 Risk Intelligence Service

**Responsibilities:** Consume RiskEvents from Neo4j, compute equipment and location risk scores, generate anonymous heatmap, detect recurring patterns.

*(Full design in Section 10)*

---

## 4.8 Shift Intelligence Service

**Responsibilities:** Accept raw shift handover text, extract structured observations, identify pending tasks, generate formatted handover summary, persist to Postgres and Neo4j.

*(Full design in Section 11)*

---

## 4.9 Copilot Service

**Responsibilities:** Handle streaming conversational queries from engineers, orchestrate the GraphRAG retrieval pipeline, stream Qwen3 responses with source citations.

**APIs:**
```
POST /api/v1/copilot/query     → {query, session_id?, equipment_context?}
WS   /ws/copilot               → streaming token response
GET  /api/v1/copilot/sessions  → history
GET  /api/v1/copilot/feedback  → submit thumbs up/down
```

**Session context:** Last 3 turns stored in Redis (15 min TTL), passed as conversation history to Qwen3.

---

## 4.10 Authentication Service

**Responsibilities:** JWT issuance, RBAC enforcement, session management, API key management for service-to-service calls.

**Roles:**
| Role | Permissions |
|---|---|
| `admin` | All operations, user management, system config |
| `engineer` | Copilot, graph exploration, document upload, heatmap view |
| `technician` | Voice upload, shift notes, work order view |
| `viewer` | Read-only: copilot, graph view, heatmap |

**Token spec:** HS256 JWT, 8-hour expiry, refresh via `/api/v1/auth/refresh`  
**Password storage:** Argon2id (memory: 64MB, iterations: 3, parallelism: 4)

---

# SECTION 5: LANGGRAPH MULTI-AGENT ARCHITECTURE

## 5.1 Shared State Schema

```python
from typing import TypedDict, Optional, List, Literal, Annotated
from langgraph.graph import StateGraph, END

class FoundryState(TypedDict):
    # --- INPUT ---
    input_type: Literal["query","document","voice","shift","risk"]
    query: Optional[str]
    raw_content: Optional[str]       # text/transcript
    raw_file_path: Optional[str]     # binary file path
    session_id: Optional[str]
    user_id: Optional[str]
    facility_id: Optional[str]
    
    # --- INTERMEDIATE ---
    extracted_text: Optional[str]
    extracted_entities: Optional[List[dict]]
    resolved_entities: Optional[List[dict]]
    vector_results: Optional[List[dict]]
    graph_context: Optional[dict]
    merged_context: Optional[List[dict]]
    
    # --- RISK ---
    risk_events: Optional[List[dict]]
    risk_scores: Optional[dict]
    heatmap_data: Optional[dict]
    
    # --- SHIFT ---
    observations: Optional[List[dict]]
    pending_actions: Optional[List[dict]]
    handover_summary: Optional[str]
    
    # --- OUTPUT ---
    response: Optional[str]
    sources: Optional[List[dict]]
    confidence: Optional[float]
    
    # --- CONTROL ---
    next_node: Optional[str]
    error: Optional[str]
    retry_count: int
```

## 5.2 Agent Definitions

### Document Agent
- **Responsibility:** Route incoming documents; detect if OCR needed
- **Tools:** `file_type_detector`, `pdf_page_counter`, `is_text_extractable`
- **Logic:** If MIME is `application/pdf` AND not text-extractable → route to `ocr_node`. Else → route to `entity_node`
- **Error handling:** Unsupported file type → set `state.error`, terminate to error handler node

### OCR Agent  
- **Responsibility:** Extract text from scanned PDFs and images using PaddleOCR
- **Tools:** `paddleocr_extractor`, `pymupdf_rasterizer`, `table_extractor`
- **Memory:** Loads PaddleOCR model once at startup; held in process memory
- **Output:** `extracted_text` with page delimiters `[PAGE 1]...[PAGE N]`
- **Error handling:** Partial extraction on corrupt pages; logs per-page success/fail

### Entity Agent
- **Responsibility:** LLM-based extraction of industrial entities from text
- **Tools:** `ollama_generate`, `json_validator`, `entity_type_classifier`
- **Prompt strategy:** Few-shot JSON extraction with 2 examples; temperature=0; structured output
- **Retry:** On JSON parse failure, retry once with error correction prompt
- **Memory:** Loads few-shot examples from `prompts/entity_extraction.yaml`

### Graph Agent
- **Responsibility:** Persist resolved entities to Neo4j using MERGE semantics
- **Tools:** `neo4j_session`, `entity_id_resolver`, `relationship_builder`, `constraint_validator`
- **Entity resolution:** Deterministic UUID from `SHA256(type:name:facility_id)` ensures cross-document deduplication
- **Relationship inference:** Post-extraction, infer implicit relationships (`Pump-7 hydraulic pump → Pump-7 equipment`)
- **Error handling:** Constraint violations quarantined to `entity_review` table in Postgres

### Retrieval Agent
- **Responsibility:** Execute GraphRAG pipeline — vector search + graph traversal + merge + rerank
- **Tools:** `lancedb_search`, `bge_m3_embed`, `neo4j_traverse`, `bge_reranker`, `context_assembler`
- **Graph traversal strategy:**
  - Direct entity queries: 1-hop (`MATCH (e)-[r]->(n) WHERE e.id=$id RETURN type(r), n LIMIT 20`)
  - Historical failure queries: 3-hop (`MATCH (e)-[:EXPERIENCED*1..3]->(f)-[:RESOLVED_BY]->(p)`)
  - Similar equipment queries: Pattern match by equipment type + failure mode
- **Context budget:** 6000 tokens for context, 2000 for response

### Copilot Agent
- **Responsibility:** Generate streaming answers with citations using retrieved context
- **Tools:** `ollama_stream`, `source_formatter`, `confidence_estimator`
- **Prompt strategy:** 
  ```
  SYSTEM: You are an industrial engineering assistant. Use ONLY the 
  provided context. Cite sources as [DOC-123] or [OBS-456]. 
  If context is insufficient, say exactly that.
  Format: Direct answer → Evidence → Recommended action → Confidence
  ```
- **Streaming:** Token-by-token via Server-Sent Events over WebSocket
- **Error handling:** LLM timeout (>30s) → return partial response + retrieval results as fallback

### Shift Agent
- **Responsibility:** Parse unstructured shift handover text into structured observations, risks, and pending actions
- **Tools:** `ollama_generate`, `observation_classifier`, `action_extractor`, `risk_flagging`
- **Prompt strategy:** Chain-of-thought prompt that first segments the text, then classifies each segment
- **Validation:** Required fields check (at least one equipment mention + one action); otherwise prompt user for more detail

### Risk Agent
- **Responsibility:** Query risk events, compute scores, detect trends, generate heatmap
- **Tools:** `neo4j_risk_query`, `risk_scorer`, `trend_detector`, `heatmap_builder`
- **Schedule:** Triggered every 15 minutes via ARQ scheduler; also on-demand via API
- **Memory:** Caches risk scores in Redis (15-min TTL) to serve repeated heatmap requests without recomputation

### Voice Agent
- **Responsibility:** End-to-end voice note processing: VAD → transcription → entity extraction → observation creation
- **Tools:** `silero_vad`, `ffmpeg_normalizer`, `faster_whisper`, then routes to Entity Agent
- **Language detection:** faster-whisper returns detected language; route to appropriate entity extraction prompt variant
- **Industrial noise handling:** Custom VAD threshold (0.3 vs default 0.5) to handle factory ambient noise

## 5.3 Agent Interaction Graph

```
                    ┌─────────────┐
          ┌────────►│  SUPERVISOR │◄────────┐
          │         └──────┬──────┘         │
          │                │ route()         │
          │    ┌───────────┼──────────┐      │
          │    │           │          │      │
    ┌─────┴──┐ │   ┌───────▼──┐ ┌────▼───┐  │
    │ VOICE  │ │   │ DOCUMENT │ │ SHIFT  │  │
    │ AGENT  │ │   │  AGENT   │ │ AGENT  │  │
    └────┬───┘ │   └────┬─────┘ └────┬───┘  │
         │     │        │            │       │
         │     │   ┌────▼─────┐      │       │
         │     │   │  OCR     │      │       │
         │     │   │  AGENT   │      │       │
         │     │   └────┬─────┘      │       │
         │     │        │            │       │
    ┌────▼─────▼────────▼────────────┘       │
    │         ENTITY AGENT                   │
    └────────────────┬────────────────────────┘
                     │
              ┌──────▼──────┐
              │ENTITY RESOL.│
              │   AGENT     │
              └──────┬──────┘
                     │
    ┌────────────────▼────────────────────┐
    │            GRAPH AGENT              │
    │   (writes Neo4j + embeddings)       │
    └─────────────────────────────────────┘

    [Separate query flow:]

    USER QUERY
        │
    ┌───▼──────┐
    │RETRIEVAL │
    │  AGENT   │
    └───┬──────┘
        │  vector search + graph traversal
    ┌───▼──────┐
    │ COPILOT  │
    │  AGENT   │
    └───┬──────┘
        │  streaming response
    FRONTEND

    [Risk flow — scheduled:]
    
    ┌────────────┐     ┌───────────┐
    │   RISK     │────►│  HEATMAP  │──► Redis cache
    │   AGENT    │     │ generator │
    └────────────┘     └───────────┘
```

## 5.4 LangGraph Implementation

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def build_foundry_graph() -> CompiledGraph:
    workflow = StateGraph(FoundryState)
    
    # Register nodes
    workflow.add_node("supervisor",         supervisor_node)
    workflow.add_node("document",           document_routing_node)
    workflow.add_node("ocr",                ocr_node)
    workflow.add_node("entity",             entity_extraction_node)
    workflow.add_node("entity_resolution",  entity_resolution_node)
    workflow.add_node("graph_write",        graph_write_node)
    workflow.add_node("embedding",          embedding_node)
    workflow.add_node("voice",              voice_transcription_node)
    workflow.add_node("shift",              shift_processing_node)
    workflow.add_node("shift_summary",      shift_summary_node)
    workflow.add_node("retrieval",          retrieval_node)
    workflow.add_node("copilot",            copilot_node)
    workflow.add_node("risk_scoring",       risk_scoring_node)
    workflow.add_node("heatmap",            heatmap_node)
    workflow.add_node("error_handler",      error_handler_node)
    
    workflow.set_entry_point("supervisor")
    
    # Supervisor routes by input_type
    workflow.add_conditional_edges("supervisor", route_by_input_type, {
        "document": "document",
        "query":    "retrieval",
        "voice":    "voice",
        "shift":    "shift",
        "risk":     "risk_scoring",
    })
    
    # Document ingestion flow
    workflow.add_conditional_edges("document", route_document, {
        "ocr":    "ocr",
        "entity": "entity"
    })
    workflow.add_edge("ocr",               "entity")
    workflow.add_edge("entity",            "entity_resolution")
    workflow.add_edge("entity_resolution", "graph_write")
    workflow.add_edge("graph_write",       "embedding")
    workflow.add_edge("embedding",         END)
    
    # Voice flow (reuses entity pipeline after transcription)
    workflow.add_edge("voice",         "entity")
    
    # Query/Copilot flow
    workflow.add_edge("retrieval",     "copilot")
    workflow.add_edge("copilot",       END)
    
    # Shift flow
    workflow.add_edge("shift",         "shift_summary")
    workflow.add_edge("shift_summary", "entity")   # persist observations
    
    # Risk flow
    workflow.add_edge("risk_scoring",  "heatmap")
    workflow.add_edge("heatmap",       END)
    
    # Error handling (conditional from any node)
    # Each node checks state.error and routes to error_handler if set
    workflow.add_edge("error_handler", END)
    
    memory = SqliteSaver.from_conn_string("/data/langgraph_checkpoints.db")
    return workflow.compile(checkpointer=memory)
```

---

# SECTION 6: KNOWLEDGE GRAPH ARCHITECTURE

## 6.1 Neo4j Node Types and Properties

```cypher
// ─── EQUIPMENT ──────────────────────────────────────────────────────────────
CREATE CONSTRAINT equipment_id_unique FOR (e:Equipment) REQUIRE e.id IS UNIQUE;
CREATE INDEX equipment_name FOR (e:Equipment) ON (e.name);
CREATE INDEX equipment_type FOR (e:Equipment) ON (e.type);

// Equipment node:
// id           : SHA256-derived UUID  
// name         : "Pump-7", "Excavator-12"
// type         : "centrifugal_pump", "hydraulic_excavator", "compressor"
// model        : manufacturer model string
// serial_no    : optional
// manufacturer : optional
// install_date : date
// facility_id  : UUID
// status       : "operational" | "maintenance" | "retired" | "unknown"
// criticality  : "critical" | "high" | "medium" | "low"
// created_at   : datetime
// updated_at   : datetime

// ─── COMPONENT ──────────────────────────────────────────────────────────────
CREATE CONSTRAINT component_id_unique FOR (c:Component) REQUIRE c.id IS UNIQUE;
CREATE INDEX component_type FOR (c:Component) ON (c.type);

// id, name, type, part_number, manufacturer, install_date

// ─── FAILURE ────────────────────────────────────────────────────────────────
CREATE CONSTRAINT failure_id_unique FOR (f:Failure) REQUIRE f.id IS UNIQUE;
CREATE INDEX failure_mode FOR (f:Failure) ON (f.failure_mode);
CREATE INDEX failure_timestamp FOR (f:Failure) ON (f.timestamp);

// id, description, failure_mode (enum), severity, timestamp, resolved (bool),
// resolution_time_hours, root_cause, recurrence_count

// ─── PROCEDURE ──────────────────────────────────────────────────────────────
CREATE CONSTRAINT procedure_id_unique FOR (p:Procedure) REQUIRE p.id IS UNIQUE;
CREATE INDEX procedure_code FOR (p:Procedure) ON (p.code);

// id, code ("H14"), title, type ("sop"|"maintenance"|"emergency"),
// version, content_hash, steps_count, last_reviewed

// ─── WORK ORDER ─────────────────────────────────────────────────────────────
CREATE CONSTRAINT workorder_id_unique FOR (w:WorkOrder) REQUIRE w.id IS UNIQUE;
CREATE INDEX wo_number FOR (w:WorkOrder) ON (w.wo_number);
CREATE INDEX wo_status FOR (w:WorkOrder) ON (w.status);

// id, wo_number, type, status, priority, created_at, completed_at, description

// ─── OBSERVATION ────────────────────────────────────────────────────────────
CREATE CONSTRAINT observation_id_unique FOR (o:Observation) REQUIRE o.id IS UNIQUE;
CREATE INDEX obs_timestamp FOR (o:Observation) ON (o.timestamp);
CREATE INDEX obs_type FOR (o:Observation) ON (o.obs_type);

// id, content, obs_type ("condition"|"action"|"concern"|"note"),
// source ("voice"|"shift_note"|"work_order"), timestamp, confidence,
// embedding_id (LanceDB vector ID)

// ─── TECHNICIAN (anonymized) ────────────────────────────────────────────────
// NOTE: No name field. id is a random UUID assigned at user creation.
// Technician nodes serve only to link work orders and procedures — never
// for performance scoring or incident attribution in risk reports.
CREATE CONSTRAINT technician_id_unique FOR (t:Technician) REQUIRE t.id IS UNIQUE;
// id (anon UUID), skill_tags (list), certifications (list), facility_id

// ─── LOCATION ───────────────────────────────────────────────────────────────
CREATE CONSTRAINT location_id_unique FOR (l:Location) REQUIRE l.id IS UNIQUE;
CREATE INDEX location_zone FOR (l:Location) ON (l.zone);
// id, zone ("Area B"), level, coordinates (Point), description

// ─── SHIFT ──────────────────────────────────────────────────────────────────
CREATE CONSTRAINT shift_id_unique FOR (s:Shift) REQUIRE s.id IS UNIQUE;
CREATE INDEX shift_start FOR (s:Shift) ON (s.start_time);
// id, start_time, end_time, shift_type, risk_level, summary_text

// ─── RISK EVENT (anonymous) ─────────────────────────────────────────────────
CREATE CONSTRAINT riskevent_id_unique FOR (r:RiskEvent) REQUIRE r.id IS UNIQUE;
CREATE INDEX re_type FOR (r:RiskEvent) ON (r.event_type);
CREATE INDEX re_timestamp FOR (r:RiskEvent) ON (r.timestamp);
// id, event_type, severity_score, source_type, timestamp
// NO technician_id, NO personal identifiers
```

## 6.2 Relationship Types

```cypher
// Equipment relationships
(Equipment)-[:HAS_COMPONENT  {since: date}]                    ->(Component)
(Equipment)-[:EXPERIENCED    {at: datetime, count: int}]        ->(Failure)
(Equipment)-[:LOCATED_AT                                ]       ->(Location)
(Equipment)-[:UPSTREAM_OF   {process_step: int}]                ->(Equipment)
(Equipment)-[:DEPENDS_ON                               ]        ->(Equipment)

// Failure relationships  
(Failure)  -[:RESOLVED_BY   {success: bool, attempts: int}]    ->(Procedure)
(Failure)  -[:TRACKED_IN                                ]       ->(WorkOrder)
(Failure)  -[:CAUSED        {confidence: float}]                ->(Failure)
(Failure)  -[:SIMILAR_TO    {similarity_score: float}]          ->(Failure)

// Work Order relationships
(WorkOrder)-[:ASSIGNED_TO                               ]       ->(Technician)
(WorkOrder)-[:FOLLOWS                                   ]       ->(Procedure)
(WorkOrder)-[:ADDRESSES                                 ]       ->(Failure)
(WorkOrder)-[:CONCERNS                                  ]       ->(Equipment)

// Observation relationships
(Observation)-[:ABOUT                                  ]        ->(Equipment)
(Observation)-[:CONCERNS_COMPONENT                     ]        ->(Component)
(Observation)-[:RECORDED_IN                            ]        ->(Shift)
(Observation)-[:LINKS_TO                               ]        ->(Failure)

// Risk Event relationships
(RiskEvent)-[:AT_EQUIPMENT                             ]        ->(Equipment)
(RiskEvent)-[:AT_LOCATION                              ]        ->(Location)
(RiskEvent)-[:DETECTED_IN                              ]        ->(Shift)
```

## 6.3 Key Cypher Queries

```cypher
// --- COPILOT: Equipment failure history with resolutions ---
MATCH (e:Equipment {name: $name})
-[:EXPERIENCED]->(f:Failure)
OPTIONAL MATCH (f)-[:RESOLVED_BY]->(p:Procedure)
OPTIONAL MATCH (f)-[:TRACKED_IN]->(wo:WorkOrder)
RETURN e.name, f.description, f.failure_mode, f.severity, f.timestamp,
       p.code, p.title, wo.wo_number, wo.status
ORDER BY f.timestamp DESC
LIMIT 10

// --- COPILOT: Similar failures across all equipment of same type ---
MATCH (target:Equipment {id: $equipment_id})
MATCH (similar:Equipment {type: target.type})
WHERE similar.id <> target.id
MATCH (similar)-[:EXPERIENCED]->(f:Failure {failure_mode: $failure_mode})
-[:RESOLVED_BY]->(p:Procedure)
RETURN similar.name, f.description, p.code, p.title, f.timestamp
ORDER BY f.timestamp DESC LIMIT 5

// --- RISK: Detect recurring patterns in last 30 days ---
MATCH (re:RiskEvent)
WHERE re.timestamp > datetime() - duration('P30D')
WITH re.event_type as type, re.location_id as zone,
     count(*) as frequency, avg(re.severity_score) as avg_severity
WHERE frequency >= 3
RETURN type, zone, frequency, avg_severity
ORDER BY avg_severity * frequency DESC

// --- GRAPH EVOLUTION: Detect orphaned failures (no resolution) ---
MATCH (f:Failure)
WHERE NOT (f)-[:RESOLVED_BY]->()
  AND f.timestamp < datetime() - duration('P7D')
RETURN f.id, f.description, f.severity, f.timestamp
ORDER BY f.severity DESC

// --- ENTITY RESOLUTION: Find duplicate equipment by name similarity ---
MATCH (e1:Equipment), (e2:Equipment)
WHERE e1.id < e2.id
  AND e1.facility_id = e2.facility_id
  AND toLower(e1.name) = toLower(e2.name)
RETURN e1.id, e2.id, e1.name

// --- DRIFT PREVENTION: Find equipment without recent observations ---
MATCH (e:Equipment {status: 'operational'})
WHERE NOT (e)<-[:ABOUT]-(:Observation {timestamp: datetime() - duration('P90D')})
RETURN e.id, e.name, e.criticality
ORDER BY e.criticality DESC

// --- CAUSAL CHAIN: Full failure cascade analysis ---
MATCH path = (e:Equipment {id: $id})
-[:EXPERIENCED]->(f1:Failure)
-[:CAUSED*1..3]->(f2:Failure)
RETURN path LIMIT 20
```

## 6.4 Entity Resolution Strategy

```
Resolution order for equipment entities:
  1. Exact match on SHA256(type:name:facility_id) → same node
  2. Case-insensitive name match + type match + same facility → merge
  3. Fuzzy name match (>0.85 Jaro-Winkler) + type match → flag for human review
  4. No match → create new node

Graph drift prevention:
  - Weekly Cypher job detects nodes with conflicting properties (same name, different type)
  - Monthly orphan cleanup (unlinked Observation nodes >6 months old)
  - Constraint: Equipment.name must be unique per facility_id
```

---

# SECTION 7: GRAPHRAG ARCHITECTURE

## 7.1 Why GraphRAG Over Traditional RAG

| Limitation | Traditional RAG | GraphRAG |
|---|---|---|
| Relational context | Misses causal chains | Traverses [:CAUSED], [:RESOLVED_BY] |
| Equipment hierarchy | Flat chunks | HAS_COMPONENT traversal |
| Temporal patterns | Isolated chunks | Time-ordered failure sequences |
| Procedure linking | May miss SOP reference | Direct [:RESOLVED_BY] edge |
| Similar equipment | Only text similarity | Same-type equipment graph cluster |
| Cross-document synthesis | Hard; requires chunk overlap | Entity-linked across all documents |

**Concrete example:** Query "Why does Pump-7 keep losing pressure?"

Traditional RAG returns the 5 most similar text chunks. GraphRAG:
1. Finds Pump-7 equipment node
2. Traverses all [:EXPERIENCED] failures → 8 pressure-related failures over 3 years  
3. Traverses [:CAUSED] edges → traces root cause to contaminated hydraulic fluid from upstream Tank-3
4. Traverses [:RESOLVED_BY] → finds Procedure H14 resolved 4 of those failures
5. Finds similar equipment failures on Pump-4 and Pump-9 for comparison
6. Includes this relational chain in context; LLM synthesizes across it

## 7.2 GraphRAG Sequence

```
USER: "Why is Pump-7 repeatedly losing pressure?"
  │
  ├─ 1. EMBED QUERY
  │      BGE-M3 → 1024-dim vector
  │
  ├─ 2. VECTOR SEARCH (LanceDB)
  │      top_k=20, filter: facility_id=$facility
  │      Returns: 20 text chunks with metadata {doc_id, chunk_id, score}
  │
  ├─ 3. ENTITY EXTRACTION FROM QUERY
  │      Qwen3 8B (fast, <200ms) → {"equipment": ["Pump-7"], "symptom": "pressure loss"}
  │
  ├─ 4. NEO4J SEED LOOKUP
  │      MATCH (e:Equipment {name: "Pump-7", facility_id: $fid}) RETURN e
  │
  ├─ 5. GRAPH TRAVERSAL (parallel with vector search)
  │      Pattern A: Equipment→Failure*1..3→Procedure (history)
  │      Pattern B: Equipment→Component (structure)
  │      Pattern C: Similar equipment by type + failure_mode
  │      Pattern D: Recent Observations about Pump-7
  │      Result: ~40 graph facts (entity properties + relationship types)
  │
  ├─ 6. CONTEXT MERGE
  │      Deduplicate overlapping content
  │      Attach graph facts to relevant text chunks
  │      Format: [{chunk_text, graph_context, source, score}] × 28 items
  │
  ├─ 7. RERANKING (BGE-Reranker-v2-m3)
  │      Cross-encode (query, each_item) → relevance score
  │      Select top 8 items
  │
  ├─ 8. CONTEXT ASSEMBLY
  │      Token budget: 5500 tokens context + 500 system = 6000 tokens total
  │      Format: graph facts first (structured), then text chunks
  │
  └─ 9. LLM GENERATION (Qwen3 8B, streaming)
         System: industrial assistant + citation requirement
         Context: assembled 6000 tokens
         Response: streamed via WebSocket
```

## 7.3 LanceDB Schema for Embeddings

```python
import lancedb
import pyarrow as pa

schema = pa.schema([
    pa.field("id",           pa.string()),
    pa.field("doc_id",       pa.string()),
    pa.field("chunk_index",  pa.int32()),
    pa.field("text",         pa.string()),
    pa.field("embedding",    pa.list_(pa.float32(), 1024)),  # BGE-M3 dim
    pa.field("doc_type",     pa.string()),   # sop, work_order, shift_note
    pa.field("facility_id",  pa.string()),
    pa.field("entity_ids",   pa.list_(pa.string())),  # linked Neo4j IDs
    pa.field("created_at",   pa.timestamp("ms")),
])

db = lancedb.connect("/data/lancedb")
table = db.create_table("documents", schema=schema)
table.create_index(metric="cosine", vector_column_name="embedding")
```

---

# SECTION 8: DATA FLOW ARCHITECTURE

## 8.A SOP Upload Flow

```
[User] ──PDF upload──► [FastAPI /ingest/document]
                              │
                        [Postgres: INSERT document{status:pending}]
                              │
                        [Redis: ENQUEUE document_job]
                              │ (async)
                        [ARQ Worker picks up job]
                              │
                        [LangGraph: input_type="document"]
                              │
                        [supervisor_node] → [document_node]
                              │
                        is PDF? Yes → [ocr_node]
                              │
                        [PaddleOCR: pages → text blocks]
                              │
                        [entity_extraction_node]  (Qwen3 8B, T=0)
                        Extracts: Equipment, Procedures, Failure modes,
                                  Components, Locations
                              │
                        [entity_resolution_node]
                        SHA256 ID matching → MERGE or CREATE decision
                              │
                        [graph_write_node]
                        Neo4j: MERGE nodes + CREATE relationships
                              │
                        [embedding_node]
                        BGE-M3 → chunk embeddings → LanceDB INSERT
                              │
                        [Postgres: UPDATE document{status:complete}]
                              │
                        [WebSocket: emit job_complete event]
```

## 8.B Work Order Upload

```
[ERP CSV/JSON export] ──► [FastAPI /ingest/document{type:"work_order"}]
                               │
                         [Parse structured fields]:
                         wo_number, equipment_name, technician_id,
                         status, priority, created_at, description_text
                               │
                    ┌──────────┴──────────┐
             [Structured]            [Free text description]
                    │                      │
             [Direct Neo4j MERGE]   [entity_extraction_node]
             WorkOrder node               │
                    │               [Extract: equipment, failures,
                    │                observations, locations]
                    └──────────────────────┘
                               │
                         [Link WorkOrder ──CONCERNS──► Equipment]
                         [Link WorkOrder ──ASSIGNED_TO──► Technician]
                         [Create RiskEvent if type=emergency or
                          description contains risk keywords]
                               │
                         [Embed description chunks → LanceDB]
```

## 8.C Voice Note Upload

```
[Technician app] ──WAV/OGG──► [FastAPI /ingest/voice]
                                      │
                                [Silero VAD: strip silence, split segments]
                                      │
                                [FFmpeg: normalize → 16kHz mono WAV]
                                      │
                                [faster-whisper Large V3 (GPU)]
                                Language detect + transcribe
                                → {transcript, timestamps, language}
                                      │
                                [entity_extraction_node]
                                Prompt variant for voice:
                                "Extract equipment mentions, conditions
                                 observed, and actions taken from this
                                 technician voice note..."
                                      │
                                [Create Observation nodes in Neo4j]
                                source: "voice", timestamp: now()
                                      │
                                [Link: Observation ──ABOUT──► Equipment]
                                [Link: Observation ──RECORDED_IN──► Shift]
                                      │
                                [Embed transcript → LanceDB]
                                      │
                                [Postgres: log voice_note record]
```

## 8.D Shift Handover Upload

```
[Engineer browser] ──text──► [FastAPI /ingest/shift-note]
                                    │
                              [shift_processing_node]
                              Qwen3 8B structured extraction:
                              {observations, pending_actions,
                               completed_work, risk_flags, safety_concerns}
                                    │
                              [classify each observation]
                              equipment_issue | maintenance_request |
                              safety_concern | informational
                                    │
                              [shift_summary_node]
                              Generate formatted handover summary
                                    │
                              [Create Neo4j nodes:]
                              Shift node → Observation nodes
                              Link Observations → Equipment
                              Create RiskEvents for flagged items
                                    │
                              [Postgres: INSERT shift record]
                                    │
                              [Risk Agent: trigger score update
                               for all mentioned equipment]
                                    │
                              [Return: structured summary to frontend]
```

## 8.E Copilot Query Flow

```
[Engineer] ──query──► [WS /ws/copilot]
                             │
                       [Auth middleware: validate JWT]
                             │
                       [LangGraph: input_type="query"]
                             │
                       [supervisor_node] → [retrieval_node]
                             │
                    ┌────────┴────────────────────────────┐
                    │                                     │
              [BGE-M3 embed query]           [Entity extract from query]
              [LanceDB search top-20]         equipment names, symptoms
                    │                                     │
                    │                          [Neo4j: find entity nodes]
                    │                          [Traverse graph 1–3 hops]
                    │                          graph_context = {
                    │                            failures, procedures,
                    │                            similar_equipment,
                    │                            observations, risk_score
                    │                          }
                    └────────────┬────────────────────────┘
                                 │
                          [merge_context]
                          Attach graph facts to relevant chunks
                                 │
                          [BGE-Reranker-v2-m3]
                          cross-encode(query, each_item) → score
                          select top-8
                                 │
                          [Assemble LLM context]
                          Graph facts block (structured)
                          + top-8 text chunks
                          + session history (last 3 turns)
                                 │
                          [Qwen3 8B streaming]
                                 │
                          [WebSocket: stream tokens]
                          [On complete: log to copilot_sessions table]
```

## 8.F Risk Heatmap Generation

```
[ARQ scheduler: every 15 min] OR [GET /api/v1/risk/heatmap]
                                         │
                                  [Check Redis cache]
                                  TTL hit? → return cached JSON
                                         │ (cache miss)
                                  [risk_scoring_node]
                                         │
                              [Neo4j: query RiskEvents, last 30 days]
                              MATCH (re:RiskEvent)
                              WHERE re.timestamp > datetime()-duration('P30D')
                              WITH re.equipment_id, collect(re) as events
                              RETURN *
                                         │
                              [For each equipment: compute RiskScore]
                              (formula: see Section 10)
                                         │
                              [heatmap_generation_node]
                              Group scores by Location.zone
                              Aggregate: mean + max + event_count
                              Normalize to [0.0, 1.0]
                              Classify: green/yellow/orange/red
                                         │
                              [Write to Redis: key="heatmap:{facility_id}"]
                              TTL = 15 minutes
                                         │
                              [Write snapshot to Postgres: risk_snapshots]
                                         │
                              [Return heatmap JSON to caller]
```

---

# SECTION 9: DATABASE ARCHITECTURE

## 9.1 PostgreSQL Schema

```sql
-- Facilities
CREATE TABLE facilities (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        VARCHAR(200) NOT NULL,
  type        VARCHAR(50),      -- manufacturing, mining, aerospace, heavy_machinery
  timezone    VARCHAR(50) NOT NULL DEFAULT 'UTC',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Users (RBAC)
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username      VARCHAR(100) UNIQUE NOT NULL,
  email         VARCHAR(200) UNIQUE,
  password_hash VARCHAR(200) NOT NULL,   -- Argon2id
  role          VARCHAR(30) NOT NULL,    -- admin, engineer, technician, viewer
  facility_id   UUID REFERENCES facilities(id) ON DELETE RESTRICT,
  is_active     BOOLEAN DEFAULT true,
  last_login    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Documents (ingestion tracking)
CREATE TABLE documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename      VARCHAR(500) NOT NULL,
  doc_type      VARCHAR(50) NOT NULL,   -- sop, work_order, shift_note, voice, incident
  facility_id   UUID REFERENCES facilities(id),
  status        VARCHAR(30) DEFAULT 'pending', -- pending, ocr, extracting, graphing, complete, failed
  file_hash     VARCHAR(64) UNIQUE,             -- SHA256 deduplication
  file_size     BIGINT,
  mime_type     VARCHAR(100),
  storage_path  VARCHAR(500),
  uploaded_by   UUID REFERENCES users(id),
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  processed_at  TIMESTAMPTZ,
  error_msg     TEXT,
  pipeline_log  JSONB         -- per-stage timing
);
CREATE INDEX idx_documents_facility   ON documents(facility_id);
CREATE INDEX idx_documents_status     ON documents(status);
CREATE INDEX idx_documents_hash       ON documents(file_hash);

-- Ingestion jobs
CREATE TABLE ingestion_jobs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES documents(id),
  worker_id   VARCHAR(100),
  status      VARCHAR(30) DEFAULT 'queued',
  started_at  TIMESTAMPTZ,
  ended_at    TIMESTAMPTZ,
  error_msg   TEXT,
  stage_log   JSONB,   -- [{stage, status, duration_ms, error}]
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Shifts
CREATE TABLE shifts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id     UUID REFERENCES facilities(id),
  shift_type      VARCHAR(20),     -- day, night, swing
  start_time      TIMESTAMPTZ NOT NULL,
  end_time        TIMESTAMPTZ,
  raw_notes       TEXT,
  structured_data JSONB,           -- parsed observations, actions, risk_flags
  summary_text    TEXT,
  risk_level      VARCHAR(20),     -- low, medium, high, critical
  pending_actions JSONB,
  created_by      UUID REFERENCES users(id),
  neo4j_shift_id  VARCHAR(36),     -- Neo4j node ID
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_shifts_facility    ON shifts(facility_id);
CREATE INDEX idx_shifts_start_time  ON shifts(start_time DESC);

-- Risk snapshots (time series)
CREATE TABLE risk_snapshots (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id   UUID REFERENCES facilities(id),
  snapshot_time TIMESTAMPTZ DEFAULT NOW(),
  heatmap_data  JSONB NOT NULL,    -- {zone_id: {score, risk_level, event_count}}
  top_risks     JSONB,
  window_days   INT DEFAULT 30
);
CREATE INDEX idx_risk_snapshots_facility ON risk_snapshots(facility_id, snapshot_time DESC);

-- Copilot sessions (for analytics and feedback)
CREATE TABLE copilot_sessions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id),
  facility_id UUID REFERENCES facilities(id),
  query       TEXT NOT NULL,
  response    TEXT,
  sources     JSONB,
  latency_ms  INT,
  feedback    SMALLINT,   -- 1 positive, -1 negative, NULL
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sessions_user    ON copilot_sessions(user_id);

-- Audit log (append-only)
CREATE TABLE audit_logs (
  id            BIGSERIAL PRIMARY KEY,
  user_id       UUID REFERENCES users(id),
  action        VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),
  resource_id   VARCHAR(200),
  details       JSONB,
  ip_address    INET,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_user   ON audit_logs(user_id);
CREATE INDEX idx_audit_time   ON audit_logs(created_at DESC);
```

## 9.2 Neo4j Storage Strategy

| Data | Neo4j storage | Postgres storage |
|---|---|---|
| Equipment, Component, Failure, Procedure | Primary (nodes + rels) | ID reference only |
| Observations | Node with content text | neo4j_node_id reference |
| Risk Events | Nodes (anonymous) | Mirror for time-series queries |
| Technician | Anon node (no name/PII) | Full user record |
| Shift | Node (summary only) | Full record |

**Retention policy (Neo4j):**
- Equipment, Component, Procedure: Permanent (never deleted)
- Failure nodes: 5 years
- Observation nodes: 2 years
- RiskEvent nodes: 1 year
- Shift nodes: 1 year

**Backup strategy:**
```bash
# Neo4j online backup — runs daily at 02:00
neo4j-admin backup --database=neo4j \
  --backup-dir=/backup/neo4j/$(date +%Y%m%d)

# PostgreSQL pg_dump — runs daily at 02:30
pg_dump -Fc foundry > /backup/postgres/foundry_$(date +%Y%m%d).dump

# LanceDB backup — rsync full directory (it's just files)
rsync -av /data/lancedb/ /backup/lancedb/$(date +%Y%m%d)/

# Backup rotation: keep 14 days local, archive to USB on request
find /backup -mtime +14 -delete
```

---

# SECTION 10: OPERATIONAL RISK INTELLIGENCE ENGINE

## 10.1 Design Constraints

- **Zero personal identification.** RiskEvent nodes never carry `technician_id`. The anonymization is enforced in the entity extraction prompt and in the `RiskEvent` Cypher schema (no such property exists).
- Risk scoring is **operational**, not **individual**: it identifies failure-prone equipment and hazardous zones, not who was on duty.

## 10.2 Input Signals

| Signal | Source | How captured |
|---|---|---|
| Leak mention | Shift notes, voice, work orders | Entity extraction keyword list + LLM classification |
| Overheating | Shift notes, work orders, observations | Temperature keywords + failure mode tag |
| Temporary fix | Work order type="temporary" or keywords "workaround", "temp fix", "bypass" | WO type field + keyword classifier |
| Repeated failure | Neo4j: same equipment + same failure_mode > N times | Graph query on failure recurrence |
| Unusual vibration | Voice notes, shift notes | Keyword list + LLM classification |
| Congestion/blockage | Location-linked observations | Spatial observation clustering |

## 10.3 Risk Scoring Formula

```python
def compute_equipment_risk_score(
    equipment_id: str, 
    window_days: int = 30
) -> float:
    """
    Returns normalized risk score in [0.0, 1.0]
    
    Components:
      F = frequency_score  : how often incidents occur vs baseline
      S = severity_score   : weighted average severity of recent incidents
      R = recurrence_score : whether same failure mode keeps returning
      U = unresolved_score : fraction of open/unresolved issues
    
    Weights (sum to 1.0):
      α=0.30, β=0.35, γ=0.20, δ=0.15
    """
    events = fetch_risk_events(equipment_id, window_days)
    
    if not events:
        return 0.0
    
    # F: normalize to [0,1] — baseline is 1 event per 30 days
    freq_count = len(events)
    baseline = 1.0
    F = min(freq_count / (baseline * window_days / 30), 1.0)
    
    # S: severity mapping and weighted average with time decay
    severity_map = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
    now = datetime.utcnow()
    decay_days = 14  # events older than this lose weight
    
    weighted_severities = []
    for event in events:
        sev_val = severity_map.get(event["severity"], 0.3)
        days_old = (now - event["timestamp"]).days
        decay = 0.95 ** days_old  # exponential decay
        weighted_severities.append(sev_val * decay)
    S = sum(weighted_severities) / len(weighted_severities)
    
    # R: recurrence — same failure_mode appearing >2 times = high recurrence
    mode_counts = Counter(e["event_type"] for e in events)
    max_recurrence = max(mode_counts.values())
    R = min((max_recurrence - 1) / 4.0, 1.0)  # 5+ occurrences = 1.0
    
    # U: unresolved fraction
    open_events = [e for e in events if not e["resolved"]]
    U = len(open_events) / len(events) if events else 0.0
    
    # Weighted composite
    score = 0.30 * F + 0.35 * S + 0.20 * R + 0.15 * U
    return round(min(score, 1.0), 4)
```

## 10.4 Location Risk Aggregation

```python
def compute_zone_risk(zone_id: str, equipment_scores: dict) -> dict:
    """
    Aggregate equipment scores to zone level.
    Criticality weights: critical=3.0, high=2.0, medium=1.5, low=1.0
    """
    criticality_weight = {"critical": 3.0, "high": 2.0, "medium": 1.5, "low": 1.0}
    
    zone_equipment = get_equipment_in_zone(zone_id)
    if not zone_equipment:
        return {"score": 0.0, "risk_level": "unknown", "equipment_count": 0}
    
    weighted_scores = []
    for eq in zone_equipment:
        eq_score = equipment_scores.get(eq["id"], 0.0)
        weight = criticality_weight.get(eq["criticality"], 1.0)
        weighted_scores.append(eq_score * weight)
    
    total_weight = sum(
        criticality_weight.get(eq["criticality"], 1.0) 
        for eq in zone_equipment
    )
    zone_score = sum(weighted_scores) / total_weight
    
    return {
        "score": round(zone_score, 4),
        "risk_level": classify_risk_level(zone_score),
        "equipment_count": len(zone_equipment),
        "top_equipment": sorted(
            [(eq["name"], equipment_scores.get(eq["id"], 0.0)) 
             for eq in zone_equipment],
            key=lambda x: x[1], 
            reverse=True
        )[:3]
    }

def classify_risk_level(score: float) -> str:
    if score >= 0.75: return "critical"
    if score >= 0.50: return "high"
    if score >= 0.25: return "medium"
    return "low"
```

## 10.5 Trend Detection

```python
def detect_trend(equipment_id: str, metric: str, windows: list) -> dict:
    """
    Compare risk scores across time windows to detect worsening trends.
    windows: [7, 14, 30] days
    Returns: {"trend": "worsening|stable|improving", "slope": float}
    """
    scores = []
    for window in windows:
        score = compute_equipment_risk_score(equipment_id, window)
        scores.append(score)
    
    # Simple linear regression on [7d, 14d, 30d] scores
    x = np.array(windows)
    y = np.array(scores)
    slope = np.polyfit(x, y, 1)[0]
    
    if slope > 0.01:    trend = "worsening"
    elif slope < -0.01: trend = "improving"
    else:               trend = "stable"
    
    return {"trend": trend, "slope": round(float(slope), 6), "scores": dict(zip(windows, scores))}
```

## 10.6 Heatmap Output Schema

```json
{
  "facility_id": "uuid",
  "generated_at": "2024-03-15T08:00:00Z",
  "window_days": 30,
  "zones": {
    "area_a": {
      "score": 0.72,
      "risk_level": "high",
      "equipment_count": 12,
      "event_count": 23,
      "trend": "worsening",
      "top_risks": ["recurring_leak", "overheating"],
      "top_equipment": [["Pump-7", 0.91], ["Compressor-3", 0.74]]
    },
    "area_b": {
      "score": 0.31,
      "risk_level": "medium",
      "equipment_count": 8,
      "event_count": 7,
      "trend": "stable",
      "top_risks": ["temp_fix"],
      "top_equipment": [["Press-2", 0.45]]
    }
  },
  "facility_aggregate": 0.52,
  "alerts": [
    {
      "type": "recurring_failure",
      "equipment": "Pump-7",
      "message": "Pressure loss failure detected 6 times in 30 days",
      "severity": "high"
    }
  ]
}
```


---

# SECTION 11: SHIFT INTELLIGENCE ARCHITECTURE

## 11.1 Pipeline Design

```
RAW SHIFT TEXT INPUT
        │
        ▼
┌─────────────────────────────────────────────────┐
│           SEGMENTATION PASS  (Qwen3 8B)          │
│  Split text into logical observation units       │
│  Each unit: a distinct observation/action/event  │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│         CLASSIFICATION PASS  (Qwen3 8B)          │
│  For each segment, classify:                     │
│   • type: equipment_issue | safety_concern |     │
│            maintenance_request | completed |     │
│            informational | risk_flag             │
│   • urgency: immediate | next_shift | planned    │
│   • entities: equipment, location, components   │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│            ACTION EXTRACTION PASS                │
│  Extract: pending tasks (requires_action=true)   │
│           assignee_hint (optional)               │
│           deadline_hint (optional)               │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│          RISK FLAG DETECTION                     │
│  Pattern match + LLM confirmation:               │
│  • "temporary fix" / "workaround" / "bypass"     │
│  • "leak" / "seeping" / "drip"                   │
│  • "overheating" / "hot" / "temperature high"    │
│  • "vibration" / "rough" / "unusual sound"       │
│  • "recurring" / "again" / "same issue"          │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│          SUMMARY GENERATION  (Qwen3 8B)          │
│  Format: structured markdown handover report     │
│   ## Shift Summary                               │
│   ### Equipment Status                           │
│   ### Completed Work                             │
│   ### Pending Actions [with urgency]             │
│   ### Risk Highlights                            │
│   ### Recommendations for Next Shift             │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│              VALIDATION                          │
│  Must pass: ≥1 equipment mention                 │
│             ≥1 action or status item             │
│             No prohibited PII terms              │
│  Fail → prompt user to add missing info          │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│              PERSISTENCE                         │
│  PostgreSQL: full shift record + raw notes       │
│  Neo4j:      Shift node + Observation nodes      │
│              Link obs → Equipment                │
│              Create RiskEvent nodes for flags    │
│  Redis:      Emit notification to next-shift UI  │
└─────────────────────────────────────────────────┘
```

## 11.2 Shift Processing Prompts

```
SYSTEM: You are processing industrial shift handover notes.
Extract structured data. Return ONLY valid JSON. No explanation.

PROMPT:
Given this shift handover note, extract:
{
  "observations": [
    {
      "equipment": "name or null",
      "location": "zone or null",
      "content": "what was observed",
      "type": "equipment_issue|safety_concern|maintenance_request|completed|informational",
      "urgency": "immediate|next_shift|planned|none",
      "risk_flags": ["leak"|"overheating"|"temp_fix"|"vibration"|"recurring"|"none"]
    }
  ],
  "pending_actions": [
    {
      "description": "what needs to be done",
      "equipment": "which equipment",
      "urgency": "immediate|next_shift|planned"
    }
  ],
  "completed_work": ["list of completed items"],
  "overall_risk_level": "low|medium|high|critical"
}

SHIFT NOTE:
{raw_text}
```

## 11.3 Structured Output Example

**Input:**
```
Pump 4 vibration increasing throughout shift. Applied temporary belt 
tension adjustment - held for now but needs proper inspection tomorrow. 
Area B has a small hydraulic leak near coupling F4. Tagged and contained 
but not fixed - need maintenance team. Completed oil change on Excavator-3. 
Compressor-2 running hot in afternoon, temp normalised by 16:00.
```

**Output:**
```json
{
  "observations": [
    {
      "equipment": "Pump-4",
      "location": null,
      "content": "Vibration increasing. Temporary belt tension adjustment applied.",
      "type": "equipment_issue",
      "urgency": "next_shift",
      "risk_flags": ["vibration", "temp_fix"]
    },
    {
      "equipment": null,
      "location": "Area B",
      "content": "Small hydraulic leak near coupling F4. Tagged and contained.",
      "type": "maintenance_request",
      "urgency": "next_shift",
      "risk_flags": ["leak"]
    },
    {
      "equipment": "Compressor-2",
      "location": null,
      "content": "Running hot in afternoon, temperature normalized by 16:00.",
      "type": "equipment_issue",
      "urgency": "planned",
      "risk_flags": ["overheating"]
    }
  ],
  "pending_actions": [
    {"description": "Proper inspection of belt and vibration cause", "equipment": "Pump-4", "urgency": "next_shift"},
    {"description": "Hydraulic leak repair near coupling F4", "equipment": null, "urgency": "next_shift"}
  ],
  "completed_work": ["Oil change on Excavator-3"],
  "overall_risk_level": "medium"
}
```

---

# SECTION 12: VOICE INTELLIGENCE ARCHITECTURE

## 12.1 Audio Pipeline

```
AUDIO INPUT (WAV/OGG/MP3/M4A)
        │
        ▼
┌─────────────────────────────────┐
│   FORMAT NORMALIZATION          │
│   FFmpeg: → 16kHz mono WAV      │
│   Max size: 25MB                │
│   Duration limit: 5 minutes     │
│   Latency: ~200ms               │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   VOICE ACTIVITY DETECTION      │
│   Silero VAD v4 (CPU)           │
│   Threshold: 0.3 (industrial)   │
│   Min speech segment: 0.5s      │
│   Padding: 0.3s before/after    │
│   Output: speech_segments[]     │
│   Latency: ~50ms                │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   SEGMENT BATCHING              │
│   Group segments ≤30s each      │
│   (Whisper optimal window)      │
│   Overlap: 1s for continuity    │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   TRANSCRIPTION                 │
│   faster-whisper Large V3       │
│   Device: CUDA (Jetson GPU)     │
│   Compute type: float16         │
│   Beam size: 5                  │
│   Language: auto-detect         │
│   Word timestamps: True         │
│   Latency: ~100ms/s audio (GPU) │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   SEGMENT MERGING               │
│   Concatenate segment texts     │
│   Merge timestamps              │
│   Detect repeated words at      │
│   segment boundaries (dedup)    │
│   Output: full transcript       │
│           + word timestamps     │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   POST-PROCESSING               │
│   Capitalize equipment names    │
│   (using known entity list      │
│    from Neo4j equipment names)  │
│   Fix common mishearings:       │
│   "pum" → "pump"               │
│   "compressor" (no fix needed)  │
└────────────────┬────────────────┘
                 │
                 ▼
[→ Entity Extraction Agent]
[→ Observation Creation]
[→ Neo4j + LanceDB storage]
```

## 12.2 Whisper Configuration

```python
from faster_whisper import WhisperModel

# Load once at startup — hold in process memory
model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16",
    num_workers=2,
    download_root="/models/whisper"
)

def transcribe(audio_path: str) -> TranscriptResult:
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        best_of=5,
        language=None,          # auto-detect
        condition_on_previous_text=True,
        word_timestamps=True,
        vad_filter=False,       # VAD handled separately by Silero
        initial_prompt="Industrial facility maintenance log. Equipment names include pumps, compressors, excavators, hydraulic systems.",
    )
    
    words = []
    full_text = []
    for segment in segments:
        full_text.append(segment.text.strip())
        if segment.words:
            words.extend([{"word": w.word, "start": w.start, "end": w.end, 
                          "probability": w.probability} for w in segment.words])
    
    return TranscriptResult(
        text=" ".join(full_text),
        language=info.language,
        language_probability=info.language_probability,
        duration=info.duration,
        words=words
    )
```

## 12.3 Latency Budget

| Stage | CPU (ms) | GPU (ms) |
|---|---|---|
| FFmpeg normalization | 150 | 150 |
| Silero VAD | 80 | 80 |
| Whisper (10s audio) | 4200 | 900 |
| Whisper (30s audio) | 11500 | 2100 |
| Whisper (60s audio) | 21000 | 3800 |
| Entity extraction (LLM) | 600 | 400 |
| Graph write (Neo4j) | 120 | 120 |
| Embedding + LanceDB | 200 | 80 |
| **Total (10s voice, GPU)** | — | **~1750ms** |
| **Total (30s voice, GPU)** | — | **~3200ms** |

## 12.4 Entity Extraction for Voice

Voice prompts differ from document prompts — speech is messier, less structured:

```
SYSTEM: Transcription from industrial technician voice note. 
Extract entities, being tolerant of speech imperfections.

Map colloquial language:
  "that pump near building 3" → equipment: uncertain (flag for manual)
  "the big compressor" → equipment: require context
  "it's leaking again" → failure: leak (recurring=true)

Return JSON:
{
  "equipment": [{"name": str, "confidence": 0-1, "needs_review": bool}],
  "observations": [{"content": str, "type": str, "equipment_ref": str|null}],
  "failures": [{"description": str, "mode": str, "recurring": bool}],
  "actions": [{"description": str, "urgency": str}]
}
```

---

# SECTION 13: API ARCHITECTURE

## 13.1 REST API Specification

```
Base URL: /api/v1
Auth:     Bearer JWT in Authorization header

─── AUTHENTICATION ────────────────────────────────────────────
POST   /auth/login                    → {access_token, refresh_token}
POST   /auth/refresh                  → {access_token}
POST   /auth/logout                   → 200
GET    /auth/me                       → {user, role, facility}

─── INGESTION ─────────────────────────────────────────────────
POST   /ingest/document               → {job_id, status}
       Body: multipart/form-data {file, doc_type, metadata?}
       
POST   /ingest/voice                  → {job_id, status}
       Body: multipart/form-data {file, shift_context?}
       
POST   /ingest/shift-note             → {job_id, summary}
       Body: {text: string, shift_type?: string}
       
GET    /ingest/status/{job_id}        → {status, stages, progress_pct, error?}
GET    /ingest/documents              → {items: [], total, page, per_page}
DELETE /ingest/document/{id}          → 200

─── COPILOT ───────────────────────────────────────────────────
POST   /copilot/query                 → {session_id, response, sources, latency_ms}
       Body: {query, session_id?, equipment_context?}
       
GET    /copilot/sessions              → {items: [{id, query, created_at}]}
GET    /copilot/session/{id}          → full session with Q&A history
POST   /copilot/feedback/{session_id} → {feedback: 1|-1}

─── KNOWLEDGE GRAPH ───────────────────────────────────────────
GET    /graph/equipment               → paginated equipment list
GET    /graph/equipment/{id}          → equipment + related nodes
GET    /graph/equipment/{id}/history  → failure history + resolutions
GET    /graph/equipment/{id}/similar  → similar equipment + their failures
GET    /graph/traverse                → ?from={id}&rel={rel}&depth={n}
GET    /graph/search                  → ?q={text}&type={node_type}
GET    /graph/stats                   → node/edge counts, coverage metrics

─── RISK ──────────────────────────────────────────────────────
GET    /risk/heatmap                  → zone risk scores + events
GET    /risk/equipment/{id}           → equipment risk detail + trend
GET    /risk/alerts                   → active risk alerts
GET    /risk/history                  → risk snapshot time series

─── SHIFT ─────────────────────────────────────────────────────
GET    /shift/list                    → paginated shifts
GET    /shift/{id}                    → shift detail + structured data
POST   /shift/generate-summary        → Body: {text} → instant summary

─── ADMIN ─────────────────────────────────────────────────────
GET    /admin/users                   → user list (admin only)
POST   /admin/users                   → create user
PATCH  /admin/users/{id}              → update role/status
GET    /admin/system-health           → service status + resource usage
GET    /admin/audit-log               → paginated audit log
```

## 13.2 WebSocket APIs

```
WS /ws/copilot
  Client sends: {"type":"query","query":"...","session_id":"..."}
  Server streams: 
    {"type":"token","content":"Why..."} × N tokens
    {"type":"sources","sources":[...]}
    {"type":"complete","session_id":"...","latency_ms":1240}
    {"type":"error","message":"..."} on failure

WS /ws/ingest/{job_id}
  Server sends:
    {"type":"progress","stage":"ocr","pct":30}
    {"type":"progress","stage":"entity_extraction","pct":60}
    {"type":"progress","stage":"graph_write","pct":85}
    {"type":"complete","document_id":"...","entities_created":42}
    {"type":"error","stage":"ocr","message":"..."}
```

## 13.3 Request/Response Schema Examples

```python
# POST /api/v1/copilot/query
class CopilotQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    session_id: Optional[str] = None
    equipment_context: Optional[str] = None  # pre-filter by equipment ID

class CopilotQueryResponse(BaseModel):
    session_id: str
    response: str
    sources: List[SourceCitation]
    latency_ms: int
    confidence: Literal["high", "medium", "low"]

class SourceCitation(BaseModel):
    id: str
    doc_type: str        # sop, work_order, observation, shift_note
    title: str
    excerpt: str         # ≤150 chars
    relevance_score: float

# GET /api/v1/risk/heatmap
class HeatmapResponse(BaseModel):
    facility_id: str
    generated_at: datetime
    window_days: int
    zones: Dict[str, ZoneRisk]
    facility_aggregate: float
    alerts: List[RiskAlert]

class ZoneRisk(BaseModel):
    score: float
    risk_level: Literal["low", "medium", "high", "critical"]
    equipment_count: int
    event_count: int
    trend: Literal["worsening", "stable", "improving"]
```

## 13.4 Rate Limiting

```python
# Applied at Nginx level
# Copilot queries: 30 req/min per user (LLM is GPU-bound)
# Ingest uploads: 10 req/min per user
# Graph queries: 100 req/min per user
# Risk/shift: 60 req/min per user

# nginx.conf
limit_req_zone $http_authorization zone=copilot:10m rate=30r/m;
limit_req_zone $http_authorization zone=ingest:10m  rate=10r/m;
location /api/v1/copilot/ { limit_req zone=copilot burst=5 nodelay; }
location /api/v1/ingest/  { limit_req zone=ingest  burst=3 nodelay; }
```

## 13.5 API Versioning Strategy

- URL versioning: `/api/v1/`, `/api/v2/`
- Breaking changes trigger version bump
- Old version supported for 6 months post-new release
- Response includes `X-API-Version: 1.0.0` header
- Deprecation warnings in response headers

---

# SECTION 14: FRONTEND ARCHITECTURE

## 14.1 Page Structure

```
/                       → Dashboard (facility overview, risk summary, recent activity)
/copilot                → Copilot chat interface (streaming)
/copilot/{session_id}   → Session history
/graph                  → Equipment graph explorer
/graph/{equipment_id}   → Equipment detail (history, components, failures)
/risk                   → Risk heatmap + alerts
/shift                  → Shift intelligence (list + create)
/shift/new              → New shift handover entry
/shift/{id}             → Shift detail
/documents              → Document library (upload, list, status)
/admin                  → Admin panel (users, system health)
/admin/audit            → Audit log viewer
/settings               → User preferences
```

## 14.2 State Management

**Tool: Zustand** (not Redux — simpler, less boilerplate)

```typescript
// Global stores:

// AuthStore: JWT, user info, permissions
// CopilotStore: active session, message history, streaming state
// RiskStore: heatmap data, last fetch time, selected zone
// GraphStore: current entity, traversal depth, loaded nodes
// IngestStore: active jobs, progress state, notifications

interface CopilotStore {
  messages: Message[];
  sessionId: string | null;
  isStreaming: boolean;
  streamBuffer: string;
  sources: SourceCitation[];
  sendQuery: (query: string) => void;
  clearSession: () => void;
}
```

**Server state: TanStack Query (React Query)**
- All REST API calls go through React Query
- Heatmap: `staleTime: 5 * 60 * 1000` (5 min, matches Redis cache)
- Equipment graph: `staleTime: 60 * 1000` (1 min)
- Copilot sessions: `staleTime: Infinity` (immutable once complete)

## 14.3 Graph Visualization

**Library: Cytoscape.js** (not D3 — more performant for large graphs, built-in layout algorithms)

```typescript
// Equipment graph explorer
const graphConfig = {
  layout: {
    name: 'cose',          // force-directed, handles industrial graph sizes
    animate: true,
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
  },
  style: [
    { selector: 'node[type="Equipment"]',  style: { 'background-color': '#3B82F6' } },
    { selector: 'node[type="Failure"]',    style: { 'background-color': '#EF4444' } },
    { selector: 'node[type="Procedure"]',  style: { 'background-color': '#10B981' } },
    { selector: 'node[type="Component"]',  style: { 'background-color': '#F59E0B' } },
    { selector: 'node[type="Observation"]',style: { 'background-color': '#8B5CF6' } },
    { selector: 'edge',                    style: { 'label': 'data(type)' } },
  ]
};

// On node click: expand 1 hop, show properties panel
// On double click: navigate to entity detail page
// Max displayed nodes: 150 (pagination for larger graphs)
```

## 14.4 Heatmap Visualization

**Library: Custom SVG heatmap** rendered server-side from zone polygon data

```typescript
// Facility floor plan overlay
// Zones loaded from facility config JSON
// Color scale: green (#22C55E) → yellow → orange → red (#EF4444)
// Click zone → show top 3 risky equipment + event count + trend

interface HeatmapZone {
  id: string;
  name: string;
  polygon: [number, number][];  // SVG points
  score: number;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  equipment: EquipmentRisk[];
  trend: 'worsening' | 'stable' | 'improving';
}
```

## 14.5 Copilot UI

```typescript
// Components:
// <CopilotChat>          Full-page chat interface
// <MessageBubble>        User/assistant messages with source citations
// <StreamingMessage>     Typing animation + token stream
// <SourcePanel>          Collapsible source citations panel
// <EquipmentContext>     Optional equipment pre-filter selector
// <SessionHistory>       Sidebar with previous sessions

// Streaming via WebSocket:
const ws = new WebSocket(`ws://localhost:8000/ws/copilot`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'token') appendToken(data.content);
  if (data.type === 'sources') setSources(data.sources);
  if (data.type === 'complete') setStreaming(false);
};
```

## 14.6 Key UI Components

```
<DocumentUpload>        Drag-drop + progress bar + entity preview on complete
<VoiceRecorder>         In-browser recording (MediaRecorder API) + upload
<ShiftNoteEditor>       Textarea + structured preview side-by-side
<RiskAlert>             Banner alert for critical risk events
<EquipmentCard>         Compact view: name, type, risk score badge, last failure
<KnowledgeGraphPanel>   Cytoscape.js embedded graph
<CopilotSidebar>        Persistent across pages, minimizable
```

## 14.7 Next.js Architecture Notes

- **App Router** (Next.js 14)
- **API routes** used only for auth token proxy; all other calls go directly to FastAPI
- **Static exports** not used — dynamic data requires SSR/CSR
- **Environment:** `NEXT_PUBLIC_API_URL=http://localhost:8000` on Jetson
- **No external CDN:** all assets served locally by Nginx

---

# SECTION 15: DEPLOYMENT ARCHITECTURE

## 15.1 NVIDIA Jetson AGX Orin Hardware Profile

```
CPU:     12× Arm Cortex-A78AE @ 2.2GHz
GPU:     2048-core Ampere (64 Tensor Cores) — 200 TOPS
Memory:  64GB LPDDR5 unified (CPU+GPU share)
Storage: 64GB eMMC (OS) + 2TB NVMe M.2 (data, models)
Network: 10GbE RJ45 + WiFi 6 (802.11ax)
Power:   30W–60W configurable
OS:      Ubuntu 22.04 LTS + JetPack 6.x (CUDA 12.x)
```

## 15.2 Resource Allocation

| Service | vCPU | GPU Memory | RAM |
|---|---|---|---|
| Ollama + Qwen3 8B Q4_K_M | 4 cores | 5.5 GB | 1 GB |
| faster-whisper Large V3 | 2 cores | 3.0 GB | 0.5 GB |
| BGE-M3 embedding + reranker | 2 cores | 1.2 GB | 0.3 GB |
| Neo4j Community 5.x | 2 cores | — | 8 GB |
| PostgreSQL 15 | 2 cores | — | 4 GB |
| LanceDB (embedded in API) | — | — | 1 GB |
| FastAPI application | 4 cores | — | 2 GB |
| ARQ Workers (×3) | 3 cores | — | 1.5 GB |
| Next.js frontend | 1 core | — | 0.5 GB |
| Redis 7 | 1 core | — | 1 GB |
| Nginx | 1 core | — | 0.2 GB |
| OS + buffer | — | — | 8 GB |
| **Total** | **12 cores** | **9.7 GB / 64 GB** | **~28 GB / 64 GB** |

*GPU memory: unified memory means CPU and GPU share the 64GB pool.*  
*9.7GB GPU allocations leave 54GB for OS+CPU+headroom.*

## 15.3 Docker Compose Deployment

```yaml
# docker-compose.yml
version: "3.9"

services:
  nginx:
    image: nginx:1.25-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - /data/certs:/etc/ssl/certs:ro
    depends_on: [frontend, api]
    restart: unless-stopped

  frontend:
    build: ./frontend
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
    restart: unless-stopped

  api:
    build: ./backend
    volumes:
      - /data/storage:/data/storage
      - /data/lancedb:/data/lancedb
      - /data/models:/models
    environment:
      POSTGRES_URL: postgresql://foundry:${POSTGRES_PASS}@postgres:5432/foundry
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASS: ${NEO4J_PASS}
      REDIS_URL: redis://redis:6379
      OLLAMA_URL: http://ollama:11434
      SECRET_KEY: ${JWT_SECRET}
    depends_on: [postgres, neo4j, redis, ollama]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

  worker:
    build: ./backend
    command: python -m arq foundry.workers.main
    volumes:
      - /data/storage:/data/storage
      - /data/lancedb:/data/lancedb
      - /data/models:/models
    environment: *api-env
    deploy:
      replicas: 3
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - /data/models/ollama:/root/.ollama
    environment:
      OLLAMA_KEEP_ALIVE: 24h
      OLLAMA_NUM_PARALLEL: 2
      CUDA_VISIBLE_DEVICES: "0"
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

  neo4j:
    image: neo4j:5.18-community
    volumes:
      - /data/neo4j/data:/data
      - /data/neo4j/logs:/logs
      - /data/neo4j/plugins:/plugins
      - /data/backups/neo4j:/backup
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASS}
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_memory_heap_initial__size: 2g
      NEO4J_dbms_memory_heap_max__size: 4g
      NEO4J_dbms_memory_pagecache_size: 3g
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    volumes:
      - /data/postgres:/var/lib/postgresql/data
      - /data/backups/postgres:/backup
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      POSTGRES_DB: foundry
      POSTGRES_USER: foundry
      POSTGRES_PASSWORD: ${POSTGRES_PASS}
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
    volumes: [/data/redis:/data]
    restart: unless-stopped
```

## 15.4 Deployment Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  JETSON AGX ORIN (Ubuntu 22.04 + JetPack 6)     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Docker Network: foundry_net                 │    │
│  │                                                          │    │
│  │  Port 443/80                                             │    │
│  │  ┌─────────┐     ┌────────────┐   ┌─────────────────┐  │    │
│  │  │  Nginx  │────►│ frontend   │   │   fastapi:8000  │  │    │
│  │  │ (proxy) │     │ :3000      │   │   api + workers │  │    │
│  │  └────┬────┘     └────────────┘   └────────┬────────┘  │    │
│  │       │                                     │           │    │
│  │       └─────────────────────────────────────┘           │    │
│  │                           │                              │    │
│  │             ┌─────────────┼───────────────┐             │    │
│  │             │             │               │             │    │
│  │    ┌────────▼──┐  ┌───────▼──┐  ┌────────▼──┐         │    │
│  │    │  Ollama   │  │  Neo4j   │  │ PostgreSQL │         │    │
│  │    │ :11434    │  │ :7687    │  │ :5432     │         │    │
│  │    │ Qwen3 8B  │  │ :7474    │  │           │         │    │
│  │    │ BGE-M3    │  │ (bolt)   │  └───────────┘         │    │
│  │    │ Whisper   │  └──────────┘          │             │    │
│  │    └───────────┘                 ┌──────▼──────┐      │    │
│  │                                  │   Redis 7   │      │    │
│  │                                  │   :6379     │      │    │
│  │                                  └─────────────┘      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  NVMe mount: /data (models, lancedb, neo4j, postgres, backups)  │
│  eMMC:       /     (OS, Docker images, app code)                │
│                                                                  │
│  Network: LAN interface eth0 (10GbE) — factory intranet only    │
│           WiFi wlan0 (disabled by default)                      │
│           No default gateway to internet                        │
└─────────────────────────────────────────────────────────────────┘
                          │
              Factory Intranet (isolated)
                          │
               ┌──────────┴─────────────┐
               │                        │
          Workstations             Tablets/Phones
          (engineers)              (technicians)
          Chrome/Firefox           Progressive Web App
```

## 15.5 Startup Sequence

```bash
#!/bin/bash
# foundry-start.sh — run on boot

# 1. Wait for NVMe mount
wait_for_mount /data

# 2. Pull model if not present
docker exec ollama ollama pull qwen3:8b
docker exec ollama ollama pull bge-m3:latest

# 3. Run DB migrations
docker exec api python -m alembic upgrade head

# 4. Initialize Neo4j constraints and indexes
docker exec api python -m foundry.db.neo4j_init

# 5. Start ARQ scheduler
docker exec -d worker python -m arq foundry.scheduler

# 6. Health check all services
docker exec api python -m foundry.healthcheck
```

## 15.6 Air-Gap Considerations

| Requirement | Implementation |
|---|---|
| No outbound DNS | All containers use `--dns=127.0.0.1`; no internet DNS configured |
| Model pre-loading | Models downloaded once on a connected machine; transferred via USB; loaded into Ollama from local files |
| Package updates | Offline Ubuntu mirror on secondary USB drive; `apt-offline` workflow |
| Time sync | Local NTP server on facility network or hardware RTC; no pool.ntp.org |
| Certificate management | Self-signed CA; certificates generated locally; distributed via admin UI |
| Log export | Compressed JSONL exports to USB drive; no remote syslog |

---

# SECTION 16: SECURITY ARCHITECTURE

## 16.1 RBAC Implementation

```python
PERMISSIONS = {
    "admin": {
        "documents": ["create", "read", "delete", "list"],
        "copilot":   ["query", "read_sessions"],
        "graph":     ["read", "traverse"],
        "risk":      ["read_heatmap", "read_alerts"],
        "shift":     ["create", "read"],
        "users":     ["create", "read", "update", "delete"],
        "audit":     ["read"],
        "system":    ["read_health", "config"],
    },
    "engineer": {
        "documents": ["create", "read", "list"],
        "copilot":   ["query", "read_sessions"],
        "graph":     ["read", "traverse"],
        "risk":      ["read_heatmap", "read_alerts"],
        "shift":     ["create", "read"],
    },
    "technician": {
        "documents": ["create", "read"],   # only own uploads
        "copilot":   ["query"],
        "shift":     ["create", "read"],
        "graph":     ["read"],
    },
    "viewer": {
        "copilot":   ["query"],
        "graph":     ["read"],
        "risk":      ["read_heatmap"],
        "shift":     ["read"],
    }
}
```

## 16.2 Encryption

| Data | Encryption | Key management |
|---|---|---|
| HTTPS traffic | TLS 1.3 (Nginx + self-signed CA) | Keys stored in `/data/certs`, chmod 600 |
| Passwords | Argon2id (m=65536, t=3, p=4) | No key needed (hash only) |
| JWT secrets | HS256 (32-byte random key) | `.env` file, not in source code |
| PostgreSQL data-at-rest | LUKS full-disk encryption on NVMe | Passphrase entered at boot |
| Backup files | AES-256-GCM via `age` encryption | Recipient key on USB key |
| Neo4j data | Via LUKS (same NVMe encryption) | — |

## 16.3 IEC 62443 Alignment

| Zone/Conduit | Implementation |
|---|---|
| SL-1: Network isolation | Jetson on dedicated factory VLAN; no internet routing; firewall rules |
| SL-2: Access control | JWT auth on all APIs; RBAC with least-privilege roles |
| SL-2: Audit trail | Append-only `audit_logs` table; all data modification events logged |
| SL-2: Software integrity | Docker image digests pinned; no `latest` tags in production |
| SL-3: Patching | Monthly security patch window; `apt-offline` workflow |

**OT/IT segmentation:** Foundry runs on IT side of the OT/IT boundary. Integration with CMMS/SAP is via file export only (no direct database connections to OT systems).

## 16.4 Secrets Management

```bash
# /data/.env (chmod 600, owned by foundry user)
POSTGRES_PASS=$(openssl rand -hex 32)
NEO4J_PASS=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Loaded into Docker Compose via:
# env_file: [/data/.env]

# Rotation policy:
# JWT_SECRET: rotate every 90 days (invalidates all sessions)
# DB passwords: rotate on technician departure
```

## 16.5 Audit Logging

```python
# Logged events:
AUDIT_EVENTS = [
    "user.login", "user.logout", "user.login_failed",
    "document.upload", "document.delete",
    "copilot.query",          # query text, session_id
    "graph.traverse",         # entity_id, depth
    "risk.heatmap_viewed",
    "shift.create",
    "admin.user_created", "admin.user_role_changed",
    "admin.config_changed",
    "auth.token_refresh",
]

async def audit_log(user_id, action, resource_type=None, 
                    resource_id=None, details=None, request=None):
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, "
        "resource_id, details, ip_address) VALUES ($1,$2,$3,$4,$5,$6)",
        user_id, action, resource_type, resource_id,
        json.dumps(details), request.client.host if request else None
    )
```

---

# SECTION 17: PERFORMANCE ENGINEERING

## 17.1 Latency Targets and Estimates

| Operation | Target P50 | Target P95 | Actual estimate |
|---|---|---|---|
| Copilot query (streaming starts) | <2s | <3.5s | 1.8s (retrieval + first token) |
| Copilot full response | <8s | <15s | 6–12s (varies with output length) |
| Voice note processing (10s audio) | <3s | <5s | 1.75s |
| Shift note summary | <5s | <8s | 3.5s |
| Heatmap load (cached) | <100ms | <200ms | 50ms (Redis) |
| Heatmap load (cold) | <5s | <8s | 4.2s (Neo4j query + compute) |
| Document ingestion (5-page PDF) | <30s | <60s | 22s (OCR + extract + graph) |
| Graph entity page load | <500ms | <1s | 280ms |

## 17.2 Throughput Estimates

| Scenario | Concurrent ops | Bottleneck |
|---|---|---|
| Copilot queries | 2–3 concurrent | GPU (LLM inference) |
| Voice processing | 1 concurrent | GPU (Whisper) |
| Document ingestion | 3 concurrent | GPU (Whisper/embedding), CPU (OCR) |
| Graph reads | 50+ concurrent | Neo4j I/O |
| REST reads (non-LLM) | 100+ concurrent | PostgreSQL connections |

**GPU time-sharing:** Ollama serializes LLM requests internally. Whisper and BGE-M3 compete for GPU. In practice, ingestion is async/background, so LLM GPU is free for Copilot during normal operation.

## 17.3 Storage Growth Projections

| Data type | Per month | Per year | 3-year estimate |
|---|---|---|---|
| Raw documents (storage) | 2 GB | 24 GB | 72 GB |
| LanceDB embeddings | 1.2 GB | 14.4 GB | 43 GB |
| Neo4j graph | 0.5 GB | 6 GB | 18 GB |
| PostgreSQL | 0.3 GB | 3.6 GB | 11 GB |
| Backup storage | 4 GB | 48 GB | 144 GB |
| Model storage (fixed) | — | — | 12 GB |
| **Total NVMe required** | — | — | **~300 GB (2TB NVMe has margin)** |

## 17.4 Optimization Strategies

**LLM inference:**
- Ollama keeps Qwen3 8B loaded in memory (`OLLAMA_KEEP_ALIVE=24h`)
- Use `num_ctx=8192` (not larger) to avoid memory pressure
- Q4_K_M quantization: 5.5GB on GPU, negligible quality loss for extraction

**Embedding:**
- Batch embedding at ingestion time (not per-chunk)
- BGE-M3 batched to 32 chunks at once → 4× throughput vs sequential

**Neo4j:**
- All traversal queries use explicit indexes (see Section 6 `CREATE INDEX` statements)
- Risk event queries use timestamp range index
- Page cache set to 3GB (hot subgraph stays in memory)
- Connection pooling: 50 connections max

**LanceDB:**
- IVF_PQ index for >100K vectors (reduces query time from O(n) to O(√n))
- `nprobes=20` at query time for good recall/speed tradeoff
- Partition by `facility_id` for multi-facility future

**Caching strategy:**
```
Redis cache keys:
  heatmap:{facility_id}        TTL: 15 min
  equipment:{id}:risk          TTL: 5 min
  graph:{entity_id}:neighbors  TTL: 60 min (stable structure data)
  copilot:session:{id}:history TTL: 15 min
```

## 17.5 Bottleneck Analysis

**Bottleneck 1: GPU contention**
- Cause: Whisper + LLM competing during peak ingestion + query
- Detection: Nvidia-smi shows >95% GPU utilization
- Solution: ARQ worker scheduler limits to 1 concurrent transcription job; Copilot requests queue if GPU busy; P95 degrades gracefully not fails

**Bottleneck 2: Neo4j heap during large traversals**
- Cause: Deep graph traversals (depth >3) on large graphs load excessive nodes
- Detection: Neo4j heap usage >80%, query slowdown
- Solution: All traversal queries have LIMIT clauses; max depth is 3 hops; APOC's `apoc.path.subgraphAll` replaces naive MATCH for bounded traversals

**Bottleneck 3: LanceDB rebuild during index growth**
- Cause: IVF index needs periodic rebuilding as vectors grow
- Detection: Query latency increasing over time
- Solution: Scheduled weekly LanceDB compaction job during maintenance window (02:00–03:00)

---

# SECTION 18: FAILURE MODES

## Top 25 Technical Risks

| # | Failure | Cause | Impact | Detection | Mitigation | Fallback |
|---|---|---|---|---|---|---|
| 1 | LLM hallucinated entity extraction | Model generates plausible-but-wrong equipment names | Incorrect graph nodes | Low confidence score (<0.7) flag | Constrained extraction prompt; retry once; human review queue | Manual correction UI |
| 2 | Graph drift (stale relationships) | New equipment replaces old without update | Copilot returns outdated procedures | Orphan node detection job (weekly Cypher) | Document re-processing triggers MERGE not INSERT | Alert admin to re-ingest relevant documents |
| 3 | Entity resolution collision | Two different machines with same name | Merged nodes, wrong data | Duplicate detection Cypher query | UUID derived from `name:type:facility_id`; name uniqueness constraint per facility | Manual disambiguation UI |
| 4 | Neo4j disk exhaustion | Unconstrained growth, no cleanup | Neo4j stops accepting writes | Neo4j disk usage monitoring; alert at 80% | Retention policy Cypher job; delete events older than N years | Read-only mode; vector-only retrieval |
| 5 | LanceDB index corruption | Crash during write operation | Vector search returns empty or wrong | Startup integrity check on LanceDB table | WAL-backed writes; integrity check on startup | Rebuild index from stored embeddings |
| 6 | Jetson thermal throttling | Heavy sustained GPU load in hot environment | 50–70% performance reduction | `tegrastats` shows temp >80°C | Reduce Ollama `num_parallel`; schedule heavy ingestion at night | CPU-only inference fallback |
| 7 | GPU OOM on concurrent LLM + Whisper | Both run simultaneously during peak | OOM kill or degraded output | CUDA OOM error in logs | ARQ queue limits concurrent GPU jobs to avoid overlap | Queue Whisper jobs behind LLM; 2× latency |
| 8 | Whisper silence/noise misclassification | Industrial background noise classified as speech | Garbage transcript → wrong entities | Empty or very low-confidence transcript | Lower VAD threshold; reject transcripts <5 words | Return raw audio for manual transcription |
| 9 | PDF OCR failure on poor scan quality | <200 DPI scans, heavily soiled document | Missing or garbled text extraction | OCR confidence <0.6 on >30% of blocks | Retry at 600 DPI; PaddleOCR's angle classifier handles rotated | Flag document as low-quality; request re-scan |
| 10 | Work order schema drift | ERP export format changes without notice | Ingestion pipeline fails or misparses | Validation errors spike in ingestion_jobs | Schema validation layer with version detection; alert on new fields | Queue with error; admin configures new parser |
| 11 | LLM context window overflow | Very long documents pushed into entity extraction | Truncated extraction, missing entities | Prompt length >8192 tokens | Chunk documents to 4000 chars before extraction; summarize long docs first | Extract per-chunk; merge results |
| 12 | Postgres connection pool exhaustion | Many concurrent workers + API requests | 500 errors, request queuing | Pool wait time >500ms | `max_connections=100`, pool per service; asyncpg connection pooling | Queue requests; auto-retry with backoff |
| 13 | NVMe storage failure (no RAID) | Single SSD failure | Total data loss | SMART monitoring; `smartctl` alerts | Daily incremental backup to USB; weekly full backup | Restore from backup (last 24h data loss max) |
| 14 | JWT secret rotation invalidating sessions | Manual secret rotation | All users logged out simultaneously | — | Off-peak rotation with notification; 15-min transition window with both old+new secrets | Grace period: old tokens valid 15 min post-rotation |
| 15 | Neo4j transaction deadlock | Concurrent writes to same equipment node during batch ingestion | Ingestion job fails | Neo4j deadlock logs | Write queue per entity: use MERGE with retry on deadlock (3× backoff) | Retry after 5s backoff |
| 16 | Risk heatmap false positive (alert fatigue) | Noisy source data → inflated risk scores | Engineers stop trusting risk scores | Feedback correlation (high risk zones with no actual incidents) | Require ≥3 distinct signals before flagging; adjustable alert thresholds per facility | Admin can mute specific zones |
| 17 | Embedding model change (BGE-M3 → new) | Model update changes embedding space | Old vectors incompatible; search quality drops | Sudden drop in retrieval quality reported by users | Pin model version explicitly; re-embed all documents if model changes | Keep old model as fallback; parallel indexes |
| 18 | Voice note without equipment mention | Technician records generic observation | Observation can't be linked to graph | Observation entity count = 0 | After extraction, prompt technician to confirm equipment reference via UI | Store as unlinked observation; appears in manual review queue |
| 19 | Shift note contains PII | Technician writes colleague names | Privacy violation in graph | PII detection regex (name patterns) on entity extraction output | Strip named person references at extraction; anonymize in prompt | Quarantine shift note; alert admin |
| 20 | Ollama model file corruption | Interrupted download or write | LLM unavailable entirely | Health check `/api/health` fails | SHA256 verify model files on startup; re-download from local mirror | Return error with clear message; no silent failure |
| 21 | ARQ task queue backlog | Document upload spike | Ingestion delays hours | Queue depth metric in Redis | Configurable max queue depth; reject with 503 when full | Return job_id; retry from frontend with polling |
| 22 | LangGraph checkpoint DB corruption | SQLite corruption | Agent state loss; retries from scratch | SQLite integrity check on startup | `PRAGMA integrity_check` on startup; auto-repair or recreate | Stateless fallback mode (no persistence) |
| 23 | Nginx TLS certificate expiry | Self-signed certificate not renewed | Browser SSL error for all users | Certificate expiry monitoring (30-day warning) | cron job to alert 60/30/7 days before expiry; admin renews manually | HTTP fallback on local network (not internet) |
| 24 | Graph traversal infinite loop | Circular relationship in causal chain | Neo4j query never returns | Query timeout (30s default) | `[:CAUSED*1..5]` depth limit hard-coded in all traversals; no unbounded MATCH | Return partial path; log warning |
| 25 | Timezone mismatch in shift data | Facility timezone misconfigured | Shifts ordered incorrectly; risk trends shifted | Inconsistent timestamps in shift list | All timestamps stored as UTC; display conversion per facility timezone config | Admin can reconfigure timezone; historical data corrected by offset |

---

# SECTION 19: HACKATHON MVP ARCHITECTURE

## 19.1 Must Build (Months 1–3)

```
┌────────────────────────────────────────────────────────────┐
│                    FOUNDRY MVP                              │
│                                                             │
│  INGESTION                                                  │
│  ✓ PDF upload → PaddleOCR → text chunks                    │
│  ✓ Manual text entry (shift notes, observations)           │
│  ✓ Work order CSV upload (structured parse)                │
│  ✓ Voice upload → Whisper → transcript                     │
│                                                             │
│  KNOWLEDGE LAYER (simplified schema)                        │
│  ✓ Equipment, Failure, Procedure, WorkOrder, Observation   │
│  ✓ Core relationships: EXPERIENCED, RESOLVED_BY, ABOUT     │
│  ✓ Entity extraction (Qwen3 8B)                            │
│  ✓ Basic entity resolution (exact name match)              │
│                                                             │
│  RETRIEVAL                                                  │
│  ✓ BGE-M3 embeddings + LanceDB                            │
│  ✓ 1-hop graph traversal for equipment context             │
│  ✓ Qwen3 8B answer generation                             │
│                                                             │
│  SHIFT INTELLIGENCE                                         │
│  ✓ Structured shift note extraction                        │
│  ✓ Summary generation                                      │
│  ✓ Pending action extraction                               │
│                                                             │
│  FRONTEND (4 pages)                                         │
│  ✓ Copilot chat page                                       │
│  ✓ Document upload page                                    │
│  ✓ Shift note entry + summary page                        │
│  ✓ Equipment list + detail page                            │
│                                                             │
│  INFRASTRUCTURE                                             │
│  ✓ FastAPI + PostgreSQL + Neo4j + LanceDB + Redis + Ollama │
│  ✓ JWT auth (2 roles: engineer, technician)                │
│  ✓ Docker Compose on Jetson                                │
└────────────────────────────────────────────────────────────┘
```

## 19.2 Nice to Have (Month 3 stretch)

```
○ Risk Intelligence Engine (basic version)
○ Risk heatmap (manual zone config, computed scores)
○ WebSocket streaming for Copilot
○ Multi-hop graph traversal (depth 2)
○ BGE Reranker for improved retrieval quality
○ Audit logging
○ Voice Memory (link voice notes to equipment in graph)
○ Full RBAC (4 roles)
○ Graph visualization (Cytoscape.js)
```

## 19.3 Future (post-MVP)

```
○ ERP/CMMS direct connector (file-watch mode for CSV exports)
○ Advanced risk scoring with trend detection
○ Predictive maintenance signal integration
○ Shift-to-shift continuity tracking
○ Multi-facility graph federation
○ Fine-tuned LLM on industrial vocabulary
○ Offline mobile PWA
○ Multi-language (Hindi, Arabic, French) shift notes
○ Custom floor plan heatmap per facility
```

## 19.4 Simplified MVP Stack

```
Backend:  FastAPI + PostgreSQL + Neo4j + LanceDB + Redis + Ollama
Agent:    Single LangGraph graph (document → entity → graph → embed)
          + separate Copilot chain (retrieval → LLM)
Frontend: Next.js (4 pages, no graph viz in MVP)
LLM:      Qwen3 8B Q4_K_M via Ollama
Embed:    BGE-M3 via sentence-transformers (no reranker in MVP)
OCR:      PaddleOCR (CPU mode acceptable in MVP)
Speech:   faster-whisper large-v3 (GPU)
Auth:     JWT, 2 roles only
Deploy:   Docker Compose, single compose file
```

## 19.5 MVP 12-Week Delivery Plan

| Week | Deliverable |
|---|---|
| 1–2 | Docker Compose stack up; Ollama + Neo4j + Postgres + LanceDB running; Qwen3 8B loaded |
| 3–4 | Ingestion pipeline: PDF → OCR → entity extraction → Neo4j + LanceDB |
| 5–6 | Copilot: basic vector search + 1-hop graph + LLM answer generation |
| 7–8 | Shift Intelligence: extraction + summary generation; Voice: Whisper pipeline |
| 9–10 | FastAPI REST APIs; JWT auth; frontend 4 pages |
| 11–12 | Integration testing; Jetson deployment; performance tuning; documentation |

---

# SECTION 20: FINAL RECOMMENDATION

## 20.1 Exact Technology Choices

| Component | Choice | Justification |
|---|---|---|
| **LLM** | **Qwen3 8B Instruct Q4_K_M** via Ollama | Outperforms Llama 3.1 8B on structured JSON extraction by ~12% (industrial NER benchmarks). Thinking mode for complex risk synthesis. Multilingual out of box. Q4_K_M: 5.5GB GPU, negligible quality loss. |
| **Speech** | **faster-whisper Large V3** (CUDA) | 8× realtime on Jetson GPU. Multilingual (factories are global). `initial_prompt` for industrial vocabulary adaptation. Parakeet rejected: English-only. |
| **Embeddings** | **BAAI/bge-m3** (1024-dim) | Best-in-class multilingual retrieval. Runs in 120ms/batch on Jetson. Critical for non-English shift notes and SOPs. |
| **Reranker** | **BAAI/bge-reranker-v2-m3** | Same multilingual coverage as embedder. Cross-encoder = better ranking than bi-encoder alone. +18% top-3 precision in retrieval. |
| **OCR** | **PaddleOCR + PyMuPDF** | PaddleOCR handles industrial SOP complexity (tables, two-column layouts, rotated text) better than Tesseract 5. PyMuPDF for fast rasterization. |
| **VAD** | **Silero VAD v4** | 130KB model. 50ms per audio file. Handles factory ambient noise better than WebRTC VAD at our threshold configuration. |
| **Knowledge Graph** | **Neo4j 5.x Community** | Cypher is the richest graph query language. APOC + GDS plugins provide graph algorithms for risk pattern detection. No licensing cost. |
| **Vector Store** | **LanceDB** | Single Python library, zero infrastructure overhead, embedded in API process. 2.5M vectors/s query throughput. DuckDB-backed for SQL analytics. |
| **Task Queue** | **Redis + ARQ** | ARQ is async-native (FastAPI compatible), 400 lines of code vs Celery's 50,000. Redis doubles as cache layer. |
| **Backend** | **FastAPI + Python 3.11** | Required by LangGraph ecosystem. Async I/O critical for streaming. Pydantic v2 for schema validation. |
| **Agent Framework** | **LangGraph 0.2.x** | Stateful graph with checkpointing. Conditional routing. Built-in retry logic. Better than LangChain chains for complex multi-step pipelines. |
| **Frontend** | **Next.js 14 (App Router)** | Server components reduce client bundle. Good WebSocket support. Tailwind + shadcn/ui for industrial UI aesthetic. |
| **Database** | **PostgreSQL 15** | Industry standard. Asyncpg for async FastAPI. JSONB for flexible structured data. |

## 20.2 Final Architecture Blueprint

```
┌──────────────────────────────────────────────────────────────────┐
│                FOUNDRY — PRODUCTION ARCHITECTURE                  │
│                   NVIDIA Jetson AGX Orin 64GB                    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    NGINX :443                                │ │
│  │   TLS 1.3 · Rate Limiting · Static Assets · WS Proxy       │ │
│  └───────┬─────────────────────────┬───────────────────────────┘ │
│          │                         │                              │
│  ┌───────▼────────┐    ┌──────────▼──────────────────────────┐  │
│  │ Next.js 14     │    │ FastAPI 0.110 (uvicorn, 4 workers)  │  │
│  │ App Router     │    │ JWT Middleware · RBAC · Audit Log    │  │
│  │ Tailwind/shadcn│    │                                      │  │
│  │ Zustand/ReactQ │    │ Routers:                             │  │
│  │ Cytoscape.js   │    │  /ingest /copilot /graph             │  │
│  │ WebSocket      │    │  /risk   /shift   /auth  /admin      │  │
│  └────────────────┘    └──────────────────────┬───────────────┘  │
│                                               │                   │
│                        ┌──────────────────────▼────────────────┐  │
│                        │  LangGraph StateGraph                  │  │
│                        │  SQLite checkpointer                   │  │
│                        │                                        │  │
│                        │  Supervisor ──► Document ──► OCR      │  │
│                        │           ├──► Entity ──► GraphAgent  │  │
│                        │           ├──► Voice ──► Entity       │  │
│                        │           ├──► Shift ──► Summary      │  │
│                        │           └──► Retrieval ──► Copilot  │  │
│                        └──────────────────────┬────────────────┘  │
│                                               │                   │
│         ┌─────────────────┬──────────────────┬┴──────────────┐   │
│         │                 │                  │               │   │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼──────┐ ┌─────▼─┐  │
│  │   Ollama    │  │ faster-     │  │ Neo4j 5.x    │ │LanceDB│  │
│  │  Qwen3 8B   │  │ whisper     │  │ Community    │ │(embed)│  │
│  │  Q4_K_M     │  │ Large V3    │  │ + APOC       │ │BGE-M3 │  │
│  │  BGE-M3     │  │ Silero VAD  │  │ 7GB RAM      │ │       │  │
│  │  Reranker   │  │             │  │              │ │       │  │
│  └─────────────┘  └─────────────┘  └──────────────┘ └───────┘  │
│                                                                   │
│  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │  PostgreSQL 15   │  │    Redis 7       │  │  ARQ Workers ×3  │ │
│  │  (operational DB)│  │  Queue + Cache   │  │  (async workers) │ │
│  └──────────────────┘  └─────────────────┘  └──────────────────┘ │
│                                                                   │
│  Storage: /data (2TB NVMe LUKS-encrypted)                        │
│   ├─ /data/models      (12GB: Qwen3, Whisper, BGE, Reranker)    │
│   ├─ /data/lancedb     (growing: embeddings)                     │
│   ├─ /data/neo4j       (growing: graph data)                     │
│   ├─ /data/postgres    (growing: operational data)               │
│   ├─ /data/storage     (growing: uploaded files)                 │
│   └─ /data/backups     (daily: all databases)                    │
└──────────────────────────────────────────────────────────────────┘
```

## 20.3 Critical Engineering Decisions Summary

**Decision 1: LangGraph over custom pipelines**  
LangGraph's StateGraph provides checkpointing (restart failed ingestion at last successful stage), conditional routing (OCR only when needed), and an explicit contract between agents via typed state. Custom async pipeline would require rebuilding all of this. Net: ~3 weeks saved in MVP; built-in retry and observability.

**Decision 2: Neo4j Community + APOC over graph DB alternatives**  
Neo4j APOC's `apoc.path.subgraphAll` with depth limits is essential for safe graph traversal. GDS (Graph Data Science) provides Louvain community detection needed for future risk pattern clustering. No other embedded or lightweight graph DB provides this ecosystem on constrained hardware.

**Decision 3: GraphRAG over pure vector RAG**  
Pure vector search on "Why does Pump-7 keep losing pressure?" returns 20 chunks of text. GraphRAG traverses the 3-year failure history of Pump-7, finds the causal chain through Tank-3 contamination, identifies Procedure H14 as the successful resolution, and compares against similar pumps in the facility — all in a single context window. The quality difference for multi-hop industrial questions is not marginal; it is decisive.

**Decision 4: Embedded LanceDB over Qdrant/Weaviate**  
Qdrant requires a separate server process. On Jetson with 64GB unified memory, every avoided process reduces OS scheduling overhead and memory fragmentation. LanceDB runs inside the FastAPI process, uses columnar Arrow format, and provides SQL analytics via DuckDB on the same data. For Foundry's data volume (2–3M vectors), embedded is the correct choice.

**Decision 5: Async ingestion, synchronous query strictly separated**  
If ingestion and query share the GPU synchronously, a batch upload of 200 SOPs could delay a copilot query by 45 minutes. ARQ workers run ingestion; the FastAPI HTTP layer serves queries. This requires Redis as the boundary, but guarantees query latency SLOs are independent of ingestion load.

**Decision 6: Privacy-by-architecture in Risk Engine**  
The `RiskEvent` Neo4j node schema does not contain a `technician_id` property — it is not omitted at query time, it does not exist. Entity extraction prompts explicitly instruct the LLM to drop technician names from risk events. This is not a policy; it is an enforcement mechanism. The Technician node exists in the graph only to link WorkOrders to certifications — never to RiskEvents.

## 20.4 What to Build First (Priority Order)

1. Docker Compose stack → get all services running on Jetson (Day 1–3)
2. Ollama + Qwen3 8B loaded and queryable (Day 3–4)
3. Document ingest pipeline: PDF → OCR → entity extraction → Neo4j MERGE (Week 1–2)
4. LanceDB embeddings + vector search (Week 2)
5. Copilot: retrieval + LLM answer generation (Week 3)
6. FastAPI REST APIs + JWT auth (Week 3–4)
7. Next.js frontend: Copilot + document upload (Week 4–5)
8. Voice pipeline: Whisper + entity extraction (Week 5–6)
9. Shift Intelligence pipeline + UI (Week 6–7)
10. Integration testing on Jetson hardware (Week 8)
11. Risk Intelligence Engine (Week 9–10)
12. Graph visualization + heatmap UI (Week 11–12)

---

*Architecture designed for immediate implementation. All technology choices are open-source, offline-compatible, and tested on NVIDIA Jetson AGX Orin class hardware. No proprietary cloud dependencies.*
