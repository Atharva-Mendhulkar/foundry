# FOUNDRY — Hackathon MVP Execution Roadmap
## Solo Builder · MacBook Air M4 24GB · AI-Assisted Development

**Architect's Note:** This roadmap is ruthlessly prioritized. The PRD describes a production system for a manufacturing plant. You are building a hackathon demo that *looks and feels* like that system. The difference matters. Every phase decision below is made with one question: *does this create demo impact faster than the alternative?*

---

## Architecture Decisions for M4 Mac Context

Before phases, lock these down — they diverge from the Jetson PRD:

| PRD Choice | Hackathon Choice | Reason |
|---|---|---|
| PaddleOCR | PyMuPDF (text PDFs) + Tesseract fallback | PaddleOCR ARM setup is fragile; 95% of demo PDFs will be text-layer anyway |
| faster-whisper CUDA | `mlx-whisper` or `openai-whisper` with MPS | M4 Metal acceleration; `mlx-whisper` is fastest on Apple Silicon |
| BGE-M3 via faster-embed | `sentence-transformers` with MPS | Works out of box on M4 |
| BGE Reranker | **Skip entirely in MVP** | Net +10% recall for 3× complexity — not worth it |
| ARQ + Redis workers | FastAPI `BackgroundTasks` → upgrade to ARQ if needed | Zero extra infrastructure at start |
| Silero VAD | Skip; pass full audio to Whisper | Whisper has internal VAD; good enough for demo |
| Argon2id | `passlib[bcrypt]` | Equivalent security, simpler dependency |
| LUKS encryption | Skip | Dev environment |
| IEC 62443 | Skip | Mention in README as "roadmap item" |

**M4-specific Ollama note:** `qwen3:8b-q4_K_M` runs at ~18 tok/s on M4 24GB. Use `OLLAMA_NUM_PARALLEL=1` to avoid contention. Pull `bge-m3` or `nomic-embed-text` as embedding model — nomic is faster on M4 and sufficient for demo.

---

---

## Phase 0 — Repository & Infrastructure Foundation

### Goal
Get the entire local stack running and verifiable. Every subsequent phase depends on this being solid. Do not skip verification steps.

### User Value
Developers can start the full stack with `docker compose up`, hit `localhost:3000`, see a login page, and confirm all services are healthy.

### Features
- Docker Compose with all 6 services (postgres, neo4j, redis, ollama, backend, frontend)
- `CLAUDE.md` with project context for AI coding sessions
- Health check endpoints for all services
- Seed data script that creates a believable fake factory
- Ollama model pull script
- Neo4j constraints and indexes initialized
- Basic JWT auth (login/logout, 2 roles: engineer, technician)
- Base Next.js scaffold with sidebar navigation

### Backend Tasks
1. `docker-compose.yml` — all services, named volumes, health checks
2. `backend/app/core/config.py` — pydantic-settings; all env vars with defaults
3. `backend/app/db/postgres.py` — SQLAlchemy async engine + session factory
4. `backend/app/db/neo4j.py` — driver singleton with connection pool
5. `backend/app/db/lancedb.py` — embedded connection, schema creation
6. `backend/alembic/versions/001_initial.py` — full Postgres schema (see Database Tasks)
7. `backend/scripts/init_neo4j.py` — CREATE CONSTRAINT + CREATE INDEX statements
8. `backend/scripts/seed_data.py` — 10 equipment nodes, 5 failure history entries, 3 SOPs (text), 2 procedures in Neo4j
9. `backend/scripts/load_models.sh` — `ollama pull qwen3:8b-q4_K_M && ollama pull nomic-embed-text`
10. `backend/app/routers/auth.py` — `/login`, `/me`, `/logout`
11. `backend/app/main.py` — FastAPI app, mount routers, lifespan startup
12. `backend/CLAUDE.md` — backend context, tech decisions, naming conventions

### Frontend Tasks
1. `npx create-next-app@latest` with TypeScript, Tailwind, App Router
2. Install: `shadcn/ui`, `zustand`, `@tanstack/react-query`, `axios`, `cytoscape`, `cytoscape-cose-bilkent`
3. `src/app/layout.tsx` — root layout with React Query provider
4. `src/app/login/page.tsx` — simple login form, JWT stored in `localStorage`
5. `src/app/dashboard/layout.tsx` — sidebar with nav items (all initially linking to `/coming-soon`)
6. `src/stores/auth.ts` — Zustand store for JWT + user info
7. `src/lib/api.ts` — Axios instance with JWT interceptor
8. `src/components/layout/Sidebar.tsx` — nav with icons for Copilot, Graph, Ingest, Shift, Risk

### Database Tasks

**PostgreSQL (Alembic migration 001_initial):**
```sql
facilities, users, documents, ingestion_jobs, shifts,
copilot_sessions, risk_snapshots, audit_logs
```
Use exact schema from PRD Section 9.1. Simplification: drop `pipeline_log JSONB` from documents for now — add in Phase 10.

**Neo4j (init script):**
- All UNIQUE constraints from PRD Section 6.1
- Indexes: `equipment_name`, `failure_mode`, `failure_timestamp`, `obs_timestamp`
- Create facility node: `(:Facility {id: "nexus-01", name: "Nexus Heavy Industries — Line 4"})`

**LanceDB (on startup):**
- Create `documents` table with schema from PRD Section 7.3
- Create `facility_id` scalar index for partition filtering

### API Contracts
```
POST /api/v1/auth/login      body: {username, password}  → {access_token, role}
GET  /api/v1/auth/me         header: Bearer JWT           → {id, username, role}
POST /api/v1/auth/logout     → 200
GET  /api/v1/health          → {status, neo4j, postgres, lancedb, ollama}
```

### Definition of Done
- [ ] `docker compose up` starts all 6 services without errors
- [ ] `GET /api/v1/health` returns `{"status":"ok"}` for all services
- [ ] Login with `engineer@nexus.com / demo1234` works, JWT returned
- [ ] Seed script creates 10 Equipment nodes visible in Neo4j Browser (`:7474`)
- [ ] Next.js dashboard layout renders at `localhost:3000/dashboard`
- [ ] All nav items render (even if pages are stubs)

### Demo Scenario
Not independently demoable. This is plumbing.

### Estimated AI-Assisted Development Time
**4–5 hours** — Docker Compose and auth are mostly boilerplate. The seed data script needs industrial domain knowledge; give Claude the PRD Section 6.1 and ask it to generate 10 realistic equipment nodes with failure history.

---

---

## Phase 1 — Knowledge Ingestion Core

### Goal
Documents become machine-readable knowledge. A user uploads a PDF (SOP, work order, incident report) and watches it get processed into entities.

### User Value
Upload a PDF → see real-time progress → see a list of extracted entities (equipment names, failure modes, procedures) when done.

### Features
- PDF upload (multipart) with SHA256 deduplication
- Text extraction: PyMuPDF for text-layer PDFs, Tesseract fallback for scanned
- Entity extraction via Qwen3 8B (constrained JSON output)
- BGE-M3 / nomic-embed-text embeddings → LanceDB
- Job status tracking in PostgreSQL
- WebSocket progress stream per job
- Upload page with drag-drop, progress tracker, entity preview on completion

### Backend Tasks
1. `backend/app/services/ocr_service.py`
   - `extract_text_pymupdf(path) → str` — try text layer first
   - `extract_text_tesseract(path) → str` — fallback for scanned PDFs
   - Returns text with `[PAGE N]` delimiters
2. `backend/app/services/llm_service.py`
   - `OllamaClient` with methods: `generate(prompt, system, temperature) → str`, `stream(...)`, `embed(text) → List[float]`
   - Use `httpx` async client against `http://ollama:11434`
3. `backend/app/services/embedding_service.py`
   - `embed_chunks(chunks: List[str]) → List[List[float]]`
   - Batch size 32; use `nomic-embed-text` via Ollama `/api/embed`
4. `backend/app/agents/state.py` — `FoundryState` TypedDict (full schema from PRD Section 5.1)
5. `backend/app/agents/nodes/entity.py`
   - `entity_extraction_node(state)` — builds few-shot prompt (Section 4.4), calls LLM, parses JSON
   - Retry once on JSON parse failure with error-correction prompt
   - Returns `state` with `extracted_entities` populated
6. `backend/app/agents/nodes/embedding.py`
   - Chunks document text at 800 chars with 100-char overlap
   - Calls embedding service
   - Writes to LanceDB
7. `backend/app/agents/nodes/supervisor.py` — routes by `input_type`
8. `backend/app/agents/nodes/document.py` — detects if OCR needed
9. `backend/app/agents/graph_builder.py` — `build_ingestion_graph()`, compile with SQLiteSaver
10. `backend/app/workers/tasks.py`
    - `process_document_job(job_id, document_id)` — invokes LangGraph ingestion graph
    - Updates `ingestion_jobs` table at each stage
11. `backend/app/routers/ingest.py`
    - `POST /ingest/document` — saves file, creates DB record, queues background task
    - `GET /ingest/status/{job_id}` — returns stage + progress
    - `GET /ingest/documents` — paginated list
    - `WS /ws/ingest/{job_id}` — emits progress events
    - Use `FastAPI BackgroundTasks` for now (no ARQ yet)

### Frontend Tasks
1. `src/app/dashboard/ingest/page.tsx` — full upload page
2. `src/components/ingest/DropZone.tsx` — react-dropzone, shows file name + size
3. `src/components/ingest/ProgressTracker.tsx` — WebSocket consumer, shows stage badges: `Queued → OCR → Extracting → Graphing → Complete`
4. `src/components/ingest/EntityPreview.tsx` — on `Complete`, shows extracted entities grouped by type (equipment, failures, procedures)
5. `src/components/ingest/DocumentList.tsx` — paginated list of uploaded docs with status badge

### Database Tasks
No new schema — uses `documents` and `ingestion_jobs` from Phase 0.

Add to documents: populate `pipeline_log JSONB` with `[{stage, status, duration_ms}]` per stage.

### API Contracts
```
POST /api/v1/ingest/document
  multipart: {file: File, doc_type: "sop"|"work_order"|"incident", metadata?: JSON}
  → {job_id: uuid, document_id: uuid, status: "queued"}

GET  /api/v1/ingest/status/{job_id}
  → {status, stages: [{name, status, duration_ms}], error?: str, entities_found?: int}

GET  /api/v1/ingest/documents
  ?page=1&per_page=20&facility_id=uuid
  → {items: [{id, filename, doc_type, status, created_at, entities_found}], total}

WS   /ws/ingest/{job_id}
  server → {"type": "progress", "stage": "ocr", "pct": 30}
  server → {"type": "complete", "entities_created": 12}
  server → {"type": "error", "stage": "entity", "message": "..."}
```

### Definition of Done
- [ ] Upload `nexus_pump_maintenance_sop.pdf` (from seed data) → job completes in <30s
- [ ] Extracted entities include at least: 2+ equipment names, 1+ procedure, 1+ failure mode
- [ ] WebSocket progress events fire for each stage
- [ ] Duplicate upload returns 409 with existing document ID
- [ ] Document list shows all uploaded files with status

### Demo Scenario
"I'm going to upload our standard pump maintenance SOP. Watch the system extract the knowledge in real-time." → drag-drop PDF → watch stages tick green → "Here are the 7 pieces of equipment, 3 procedures, and 4 failure modes the system automatically identified."

### Estimated AI-Assisted Development Time
**8–10 hours** — the entity extraction prompt engineering and JSON retry logic are the hard parts. LangGraph graph builder is mostly boilerplate once state is defined. WebSocket progress stream takes 1–2 hours to get right.

---

---

## Phase 2 — Knowledge Graph Foundation

### Goal
Extracted entities become persistent, queryable nodes in Neo4j. Users can browse the knowledge graph visually.

### User Value
After uploading documents, users see a live force-directed graph of equipment, failures, and procedures. Clicking a node shows its relationships and properties.

### Features
- Entity resolution (SHA256 UUID + case-insensitive name deduplication)
- Neo4j MERGE for all entity types: Equipment, Failure, Procedure, WorkOrder, Observation
- Relationship creation: EXPERIENCED, RESOLVED_BY, HAS_COMPONENT, ABOUT
- Graph explorer page with Cytoscape.js
- Equipment detail page: full failure history, linked procedures, recent observations
- Work order CSV bulk import

### Backend Tasks
1. `backend/app/services/graph_service.py`
   - `resolve_entity_id(type, name, facility_id) → uuid` — SHA256 deterministic ID
   - `upsert_equipment(entity, facility_id)` — MERGE pattern
   - `upsert_failure(entity, equipment_id)` — MERGE + link EXPERIENCED
   - `upsert_procedure(entity)` — MERGE
   - `link_failure_to_procedure(failure_id, procedure_id, success)` — RESOLVED_BY
   - `upsert_observation(entity, equipment_ids)` — MERGE + link ABOUT
   - `get_equipment_subgraph(equipment_id, depth=2) → dict` — returns nodes + edges for frontend
   - `get_equipment_history(equipment_id) → list` — failures + resolutions
   - `get_similar_equipment(equipment_id) → list` — same type, different ID
   - `search_entities(query, node_type?) → list` — case-insensitive name search
2. `backend/app/agents/nodes/entity_resolution.py`
   - `entity_resolution_node(state)` — calls `resolve_entity_id` for each extracted entity
   - Flags low-confidence matches (Jaro-Winkler >0.85 but <0.95) for review
3. `backend/app/agents/nodes/graph_write.py`
   - `graph_write_node(state)` — calls graph_service to persist all resolved entities + relationships
4. Wire Phase 1 LangGraph: add `entity_resolution` → `graph_write` → `embedding` edge
5. `backend/app/routers/graph.py`
   - All graph endpoints (see API Contracts)
6. Work order CSV importer: `POST /api/v1/ingest/workorders-csv` — parse CSV, ingest each row through abbreviated pipeline

### Frontend Tasks
1. `src/components/graph/GraphCanvas.tsx`
   - Cytoscape.js with `cose-bilkent` layout
   - Node colors: Equipment=#3B82F6, Failure=#EF4444, Procedure=#10B981, Component=#F59E0B, Observation=#8B5CF6
   - Edge labels: relationship type
   - On node click: show `<EntitySidebar>` with properties
   - On node double-click: navigate to detail page
   - Controls: zoom in/out, fit, reset, filter by node type
   - Max 150 nodes (pagination warning above threshold)
2. `src/app/dashboard/graph/page.tsx` — full-page graph explorer with search bar + type filter pills
3. `src/app/dashboard/graph/[id]/page.tsx` — equipment detail page:
   - Header: name, type, status badge, criticality badge
   - Tabs: Overview | Failure History | Linked Procedures | Recent Observations
   - Mini-graph: 1-hop neighborhood of this node
4. `src/components/graph/EntitySearch.tsx` — debounced search → hits `/graph/search`
5. `src/components/graph/FailureTimeline.tsx` — vertical timeline of failures with severity color coding

### Database Tasks
No new Postgres schema. Neo4j gains full population from ingested documents.

Add Postgres view for quick stats:
```sql
CREATE VIEW graph_stats AS
SELECT
  (SELECT count FROM neo4j_counts WHERE label='Equipment') as equipment_count,
  -- populated via periodic Neo4j → Postgres sync in background task
  ...
```
Simpler: add `graph_entity_counts` table updated by background task every 5 min.

### API Contracts
```
GET /api/v1/graph/equipment
  ?page&per_page&search&status&criticality
  → {items: [EquipmentSummary], total}

GET /api/v1/graph/equipment/{id}
  → {node: Equipment, components: [], recent_failures: [], risk_score: float}

GET /api/v1/graph/equipment/{id}/history
  → [{failure, resolved_by_procedure, work_order, timestamp}]

GET /api/v1/graph/equipment/{id}/similar
  → [{equipment, shared_failure_modes: [], common_procedures: []}]

GET /api/v1/graph/traverse
  ?from={id}&depth=2&rel_types=EXPERIENCED,RESOLVED_BY
  → {nodes: [GraphNode], edges: [GraphEdge]}

GET /api/v1/graph/search
  ?q={text}&type={Equipment|Failure|Procedure|all}
  → {results: [{id, label, type, match_score}]}

GET /api/v1/graph/stats
  → {equipment_count, failure_count, procedure_count, relationship_count, coverage_pct}

POST /api/v1/ingest/workorders-csv
  multipart: {file: CSV}
  → {job_id, rows_queued}
```

### Definition of Done
- [ ] Upload 3 documents → 10+ Equipment nodes appear in Neo4j with EXPERIENCED relationships
- [ ] Graph page renders nodes with correct colors; edges labeled
- [ ] Equipment detail page shows failure timeline for Pump-7
- [ ] Work order CSV import creates `WorkOrder` nodes linked to `Equipment`
- [ ] `/graph/stats` returns non-zero counts
- [ ] Search for "Pump" returns matching equipment nodes

### Demo Scenario
"Every document we've ingested has built out this knowledge graph automatically." → Show graph page with clustered nodes → Click Pump-7 → "Here's every failure it's experienced, the procedures that resolved them, and when it last had maintenance." → Show failure timeline.

### Estimated AI-Assisted Development Time
**7–8 hours** — Cytoscape.js setup and MERGE Cypher patterns take most of the time. Entity resolution logic is straightforward once the SHA256 ID pattern is clear.

---

---

## Phase 3 — Foundry Copilot V1

### Goal
Engineers can ask natural language questions about equipment and procedures and get answers grounded in the knowledge graph — not hallucinated. This is the crown jewel of the demo.

### User Value
"What procedure resolved the last pressure failure on Pump-7?" → streaming answer with inline citations pointing to specific documents and graph nodes.

### Features
- Hybrid GraphRAG: vector search (LanceDB) + graph traversal (Neo4j) + merged context
- Qwen3 8B streaming response via WebSocket with token-by-token delivery
- Source citations rendered inline in response (e.g., `[SOP-H14]`, `[OBS-2024-03]`)
- Session memory: last 3 turns stored in Redis/in-memory
- Equipment context pre-filter (narrow search to one machine)
- Streaming chat UI with typing indicator
- Thumbs up/down feedback

### Backend Tasks
1. `backend/app/agents/nodes/retrieval.py` — **the most important node in the system**
   - Step 1: embed query via nomic-embed-text
   - Step 2: LanceDB search `top_k=20`, filter by `facility_id`
   - Step 3: extract entity names from query (fast Qwen3 call, temp=0, <300ms)
   - Step 4: Neo4j seed lookup (find Equipment node matching extracted name)
   - Step 5: 3-pattern graph traversal (equipment history, components, similar equipment)
   - Step 6: merge + deduplicate vector chunks and graph facts
   - Step 7: **skip reranker** — use score-based top-8 selection
   - Step 8: assemble context string with token budget 5500
2. `backend/app/agents/nodes/copilot.py`
   - Build system prompt (from PRD Section 5.2 Copilot Agent)
   - Ollama streaming call
   - Source citation extraction from response
3. `backend/app/routers/copilot.py`
   - `POST /api/v1/copilot/query` — non-streaming for simple clients
   - `WS /ws/copilot` — full streaming WebSocket
   - Session history: `Dict[session_id, List[turns]]` stored in-process (Redis later)
4. Wire LangGraph query flow: `supervisor → retrieval → copilot → END`
5. Add session logging to `copilot_sessions` table

### Frontend Tasks
1. `src/components/copilot/ChatInterface.tsx` — full chat UI
   - Message list (scrollable)
   - Input bar with send button
   - Streaming message with cursor animation
   - Equipment context selector (optional dropdown pre-filter)
   - New chat / history selector
2. `src/components/copilot/MessageBubble.tsx`
   - User message: right-aligned, dark background
   - Assistant message: left-aligned, with inline citation highlights
   - Citation badges rendered as clickable chips (e.g. `[SOP-H14]`)
3. `src/components/copilot/SourcePanel.tsx` — collapsible panel below each response listing full source metadata
4. `src/stores/copilot.ts` — Zustand: messages[], sessionId, isStreaming, streamBuffer
5. `src/app/dashboard/copilot/page.tsx` — full page layout
6. WebSocket client: `src/lib/ws.ts` — handles connect, disconnect, message parsing, reconnect

### Database Tasks
Populate `copilot_sessions` table with query, response, sources JSON, latency_ms, feedback (nullable).

### API Contracts
```
POST /api/v1/copilot/query
  body: {query: str, session_id?: str, equipment_context?: str}
  → {session_id, response, sources: [{id, doc_type, title, excerpt, score}],
     latency_ms, confidence: "high"|"medium"|"low"}

POST /api/v1/copilot/feedback/{session_id}
  body: {feedback: 1|-1}
  → 200

GET  /api/v1/copilot/sessions
  → {items: [{id, query, created_at, feedback}]}

WS   /ws/copilot
  client → {"type":"query","query":"...","session_id":"...","equipment_context":"..."}
  server → {"type":"token","content":"..."}   (× N)
  server → {"type":"sources","sources":[...]}
  server → {"type":"complete","session_id":"...","latency_ms":2100}
  server → {"type":"error","message":"..."}
```

### Definition of Done
- [ ] "What are the common failure modes for Pump-7?" returns an answer grounded in ingested SOPs — not a generic LLM response
- [ ] Response streaming begins within 2.5s of submitting query
- [ ] At least 2 source citations appear per response when relevant docs exist
- [ ] "I don't have information about that" returned when query has no relevant context (not a hallucination)
- [ ] 3-turn session memory works: follow-up "what procedure handles that?" correctly refers to context from previous turn
- [ ] Thumbs up/down records feedback in DB

### Demo Scenario
"Watch what happens when I ask this." → type "Why does Pump-7 keep losing pressure and what's the resolution?" → streaming answer begins, watch tokens appear → "Notice it cites the specific SOP and the work order from last March. This is not a general AI answer — it's grounded in your facility's actual history." → Show source panel.

### Estimated AI-Assisted Development Time
**10–12 hours** — the retrieval node is the most complex piece in the entire system. Graph traversal + vector merge + context assembly will require iteration. WebSocket streaming in FastAPI + Next.js takes 2 hours to get right end-to-end.

---

---

## Phase 4 — Voice Intelligence

### Goal
Technicians can upload a voice recording from their phone. It becomes a structured observation linked to the knowledge graph within seconds.

### User Value
Upload a 30-second voice memo → get a timestamped transcript → system identifies "Pump-7" and "hydraulic leak" → creates an Observation node automatically linked to Pump-7 in the graph.

### Features
- Audio upload: WAV, MP3, M4A, OGG via multipart
- Transcription: `mlx-whisper` (preferred on M4) or `openai-whisper`
- Post-processing: capitalize known equipment names from Neo4j entity list
- Voice-specific entity extraction (tolerant of speech messiness)
- Observation node creation → linked to equipment in graph
- Browser voice recorder (MediaRecorder API) for live demo
- Voice note list with playback

### Backend Tasks
1. `backend/app/services/whisper_service.py`
   - Load model once at startup: `mlx_whisper.transcribe(audio_path, path_or_hf_repo="mlx-community/whisper-large-v3-mlx")` or fallback `whisper.load_model("medium")`
   - `transcribe(audio_path: str) → TranscriptResult` — text + language + segments + word timestamps
   - Equipment name post-processing: fetch all Equipment names from Neo4j, title-case matches in transcript
2. `backend/app/agents/nodes/voice.py`
   - FFmpeg normalize to 16kHz mono WAV (subprocess call)
   - Call whisper_service
   - Use voice-specific entity extraction prompt (from PRD Section 12.4) — more lenient, marks uncertain refs with `needs_review: true`
   - Create Observation nodes for each extracted observation
   - Link to Equipment nodes where confident; flag uncertain for manual review
3. Wire LangGraph: `supervisor → voice → entity → entity_resolution → graph_write → embedding`
4. `backend/app/routers/ingest.py` — add `POST /api/v1/ingest/voice`

### Frontend Tasks
1. `src/components/ingest/VoiceUploader.tsx` — file upload + MediaRecorder live recording
   - Record button (uses browser mic)
   - Recording timer + waveform visualization (Web Audio API)
   - Upload and process button
   - Transcript preview on completion
   - Extracted entities list
2. Add voice tab to ingest page
3. `src/components/ingest/VoiceNoteList.tsx` — list of past voice notes with transcript previews and linked equipment

### Database Tasks
`documents` table already handles voice (`doc_type: "voice"`). No new schema needed.

Add to Neo4j seed: 3 pre-processed voice observations linked to Pump-7 and Compressor-3 (demonstrates the feature without live recording in demo).

### API Contracts
```
POST /api/v1/ingest/voice
  multipart: {file: audio_file, shift_context?: str}
  → {job_id, status: "queued"}

GET  /api/v1/ingest/voice/{job_id}
  → {status, transcript?: str, language?: str, observations_created?: int, entities: [...]}
```

### Definition of Done
- [ ] Upload a 20-second voice memo saying "Pump Seven has been vibrating unusually since this morning, sounds like a bearing issue" → transcript appears with "Pump-7" correctly capitalized
- [ ] Observation node created in Neo4j: `(Observation)-[:ABOUT]->(Equipment {name: "Pump-7"})`
- [ ] Voice note appears in ingest list with transcript preview
- [ ] Browser recorder works: click Record → speak → click Stop → upload → transcribe
- [ ] Uncertain equipment references (e.g. "that big pump near the door") flagged with `needs_review: true`

### Demo Scenario
"Our technicians don't fill out forms — they just leave a voice note." → Open phone, play a pre-recorded voice memo → upload it → "30 seconds later, that observation is in the knowledge graph, linked to the right equipment, searchable through the Copilot."

### Estimated AI-Assisted Development Time
**5–6 hours** — Whisper setup on M4 is the main risk. MediaRecorder browser API works well. Voice entity extraction prompt needs tuning.

---

---

## Phase 5 — Shift Intelligence

### Goal
Engineers can submit an unstructured shift handover note and get a structured summary with pending actions, risk flags, and equipment observations — automatically persisted to the knowledge graph.

### User Value
Paste a messy end-of-shift note → receive a formatted handover report with sections: Equipment Status, Completed Work, Pending Actions, Risk Highlights, Recommendations for Next Shift.

### Features
- Shift note submission (text area)
- Multi-pass extraction: segment → classify → action extract → risk flag (Section 11.1)
- Summary generation in structured markdown
- Pending actions with urgency tags
- Risk flag detection: leak, overheating, temp_fix, vibration, recurring
- Shift node + Observation nodes in Neo4j
- Shift history list

### Backend Tasks
1. `backend/app/agents/nodes/shift.py`
   - `shift_processing_node(state)` — calls Qwen3 with shift extraction prompt (Section 11.2)
   - Returns `state.observations`, `state.pending_actions`, `state.risk_events`
   - `shift_summary_node(state)` — generates formatted markdown summary
   - Validation: must have ≥1 equipment mention + ≥1 action item
2. Wire LangGraph: `supervisor → shift → shift_summary → entity → entity_resolution → graph_write → embedding`
3. `backend/app/routers/shift.py`
   - `POST /api/v1/shift/` — submit shift note, returns structured JSON + summary
   - `GET /api/v1/shift/` — paginated shift history
   - `GET /api/v1/shift/{id}` — shift detail
   - `POST /api/v1/shift/generate-summary` — instant preview (no persistence) for live demo

### Frontend Tasks
1. `src/app/dashboard/shift/new/page.tsx`
   - Split-pane layout: left = text editor, right = live preview
   - Submit button → right pane populates with structured summary
   - Pending actions rendered as checklist items with urgency badges (🔴 Immediate, 🟡 Next Shift, 🟢 Planned)
   - Risk flag chips: LEAK, OVERHEATING, TEMP_FIX, VIBRATION, RECURRING
2. `src/components/shift/ShiftEditor.tsx` — textarea with character count
3. `src/components/shift/SummaryView.tsx` — renders structured JSON as formatted report
4. `src/app/dashboard/shift/page.tsx` — shift history list with risk level badges

### Database Tasks
Populate `shifts` table: `raw_notes`, `structured_data JSONB`, `summary_text`, `risk_level`, `pending_actions JSONB`.

Add 3 pre-seeded shift records so history list isn't empty on demo day.

### API Contracts
```
POST /api/v1/shift/
  body: {text: str, shift_type?: "day"|"night"|"swing"}
  → {shift_id, summary_text, structured_data: {observations, pending_actions,
     completed_work, overall_risk_level}, risk_flags: [str], entities_created: int}

POST /api/v1/shift/generate-summary
  body: {text: str}
  → same as above, no DB write (demo preview mode)

GET  /api/v1/shift/
  ?page&per_page
  → {items: [{id, start_time, risk_level, pending_actions_count, summary_text}]}

GET  /api/v1/shift/{id}
  → full shift record
```

### Definition of Done
- [ ] Submit the sample shift note from PRD Section 11.3 → receive JSON matching the example output
- [ ] Summary renders with all 5 sections populated
- [ ] Pump-4 vibration observation creates an `Observation` node linked to Pump-4 in Neo4j
- [ ] "Area B hydraulic leak" creates a `RiskEvent` node in Neo4j
- [ ] Shift appears in history list with "medium" risk level badge
- [ ] Copilot can answer "What were the risk items from the last shift?" (integration test)

### Demo Scenario
"Let me show you end-of-shift handover." → paste the messy example note into the editor → "The system is now extracting structure from plain English." → watch the right pane populate with the formatted report → "Pump-4 is flagged for vibration inspection. That observation is now in the knowledge graph and the next engineer's Copilot will surface it automatically."

### Estimated AI-Assisted Development Time
**5–6 hours** — the multi-pass extraction prompt (segment → classify → summarize) is the core work. Split-pane UI with live preview is straightforward.

---

---

## Phase 6 — Operational Memory Dashboard

### Goal
A unified overview that makes the facility's operational state visible at a glance. This is the first page judges see — it needs to look like a real product.

### User Value
Log in and immediately understand: current risk levels, recent activity, graph coverage metrics, pending actions across all shifts.

### Features
- Stat cards: Equipment count, Observations this week, Pending actions, Graph coverage %
- Recent activity feed (ingestion events, shift submissions, risk alerts)
- Equipment status grid: each machine as a card with risk badge
- Pending actions across all shifts (consolidated list)
- Quick-access: "Ask Copilot" shortcut, "New Shift Note" button
- Graph coverage metric: % of equipment with ≥1 linked SOP

### Backend Tasks
1. `backend/app/routers/admin.py` — `GET /api/v1/admin/system-health` for service status
2. Add to graph_service: `get_dashboard_stats()` — single Neo4j query returning all counts
3. Add: `get_recent_activity(limit=20)` — combines documents, shifts, voice notes sorted by time
4. Add: `get_pending_actions(facility_id)` — aggregates `pending_actions` JSONB from all shifts
5. Add: `get_equipment_coverage()` — % of Equipment nodes with ≥1 linked Procedure

### Frontend Tasks
1. `src/app/dashboard/page.tsx` — full dashboard layout
2. `src/components/dashboard/StatCard.tsx` — icon + number + trend arrow
3. `src/components/dashboard/ActivityFeed.tsx` — real-time-looking activity list
4. `src/components/dashboard/EquipmentGrid.tsx` — 3-column grid of `<EquipmentCard>`s
5. `src/components/dashboard/PendingActions.tsx` — consolidated action list with urgency filter
6. `src/components/layout/TopBar.tsx` — facility name, user menu, notification bell

### Database Tasks
None — this phase reads existing data.

Add Redis cache for dashboard stats (`TTL: 2 min`) to avoid Neo4j hammering on page refresh.

### API Contracts
```
GET /api/v1/graph/stats
  → {equipment_count, failure_count, procedure_count, obs_count,
     coverage_pct, last_updated}

GET /api/v1/activity
  ?limit=20
  → {items: [{type, title, description, created_at, entity_id?}]}

GET /api/v1/shift/pending-actions
  → {items: [{description, equipment, urgency, shift_id, shift_date}]}
```

### Definition of Done
- [ ] Dashboard loads in <500ms with real data (not placeholder text)
- [ ] Stat cards show accurate counts matching Neo4j state
- [ ] Activity feed updates after uploading a new document (no manual refresh needed — or manual refresh is acceptable for demo)
- [ ] Equipment grid shows all 10 seeded machines with status badges
- [ ] Coverage % is non-zero and reflects actual procedure linkages

### Demo Scenario
"Here's the operational overview of Nexus Line 4." → open dashboard → walk through stats → "This is what happens when institutional memory becomes machine-readable. Every piece of knowledge we've ingested for the last decade is accessible in seconds."

### Estimated AI-Assisted Development Time
**5–6 hours** — primarily frontend work. The backend is aggregation queries on existing data.

---

---

## Phase 7 — Risk Intelligence

### Goal
Surface which equipment and zones are at elevated risk based on patterns in the historical data, with a visual heatmap.

### User Value
A color-coded facility map showing red zones (critical risk) to green zones (low risk), with drill-down to see which machines are driving the risk and why.

### Features
- Risk scoring formula from PRD Section 10.3 (frequency × severity × recurrence × unresolved fraction)
- Per-equipment risk scores stored in Redis (TTL 15 min)
- Zone aggregation with criticality weighting (Section 10.4)
- SVG heatmap with hardcoded Nexus facility zones (5 zones)
- Risk alerts list: recurring failures, unresolved critical issues
- Trend indicator per equipment (worsening / stable / improving)

### Backend Tasks
1. `backend/app/services/risk_service.py`
   - `compute_equipment_risk_score(equipment_id, window_days=30) → float`
   - `compute_zone_risk(zone_id, equipment_scores) → dict`
   - `classify_risk_level(score) → str`
   - `detect_trend(equipment_id) → dict`
   - `generate_heatmap(facility_id) → HeatmapJSON`
2. `backend/app/routers/risk.py`
   - `GET /api/v1/risk/heatmap` — check Redis cache, generate if miss
   - `GET /api/v1/risk/equipment/{id}` — equipment risk detail + trend
   - `GET /api/v1/risk/alerts` — threshold-based alerts
3. Add ARQ scheduled job: recompute heatmap every 15 min (or use `asyncio.create_task` on startup)
4. Seed: add 15–20 `RiskEvent` nodes to Neo4j that create an interesting heatmap (some equipment in "Area A" with multiple events)

### Frontend Tasks
1. `src/components/risk/HeatmapZones.tsx`
   - SVG with 5 hardcoded zone polygons (Area A–E)
   - Zone fill color from risk score (green → yellow → orange → red)
   - Click zone → slide-up panel with top 3 risky machines, event counts, trend
2. `src/components/risk/RiskCard.tsx` — equipment risk detail with score gauge
3. `src/components/risk/AlertBanner.tsx` — critical alert banner at top of risk page
4. `src/app/dashboard/risk/page.tsx` — heatmap + alerts side-by-side
5. `public/facility-zones.json` — hardcoded Nexus plant zone polygons (invent a reasonable layout)

### Database Tasks
Add `risk_snapshots` table (already in Phase 0 schema). Write snapshot after each heatmap generation.

### API Contracts
```
GET /api/v1/risk/heatmap
  → HeatmapJSON (full schema from PRD Section 10.6)

GET /api/v1/risk/equipment/{id}
  → {equipment_id, name, risk_score, risk_level, trend, events: [...],
     top_failure_modes: [...], unresolved_count: int}

GET /api/v1/risk/alerts
  → {alerts: [{type, equipment, message, severity, created_at}]}
```

### Definition of Done
- [ ] Heatmap renders with correct color zones based on seed data
- [ ] "Area A" shows high risk (Pump-7 drives it) with red fill
- [ ] Click Area A → see Pump-7 at 0.91 risk score
- [ ] Trend detection shows Pump-7 as "worsening"
- [ ] Risk alert appears: "Pump-7: Pressure loss failure detected 6 times in 30 days"

### Demo Scenario
"This is our risk heatmap." → show heatmap with one red zone → "Area A is critical because Pump-7 has had the same pressure failure 6 times this month. The system identified this pattern automatically — without any manual configuration." → click zone → drill down to equipment.

### Estimated AI-Assisted Development Time
**5–6 hours** — risk scoring math is straightforward Python. SVG heatmap needs 1–2 hours of careful coordinate work. The seeded data matters a lot for demo quality.

---

---

## Phase 8 — Expertise Graph

### Goal
Map who knows what. Which technicians have worked on which equipment, and what skills are implicitly demonstrated by their work history.

### User Value
Search for "who has experience with hydraulic pump failures" → see ranked list of anonymous technicians with relevant skill tags and their work history.

### Features
- Technician nodes: anonymous UUID-based (no names — enforced by design)
- Skill tags derived from completed work orders (e.g., "hydraulic_systems", "vibration_diagnosis")
- Expertise search: find technicians with relevant skills for a given failure mode
- Work history visualization: technician → procedures performed → equipment worked on

### Backend Tasks
1. Extend `graph_service.py`: `upsert_technician(anon_id, skill_tags, certifications)`
2. Wire to work order ingestion: extract technician from WO, strip name, use anonymized ID
3. `GET /api/v1/graph/expertise?skill=hydraulic_systems` → ranked technician list
4. `GET /api/v1/graph/technician/{id}/history` → work orders + procedures

### Frontend Tasks
1. `src/app/dashboard/graph/page.tsx` — add "Expertise" tab to graph explorer
2. Skill filter search in graph: filter nodes by technician + skill tag

### Database Tasks
No new schema — Technician nodes live in Neo4j.

### API Contracts
```
GET /api/v1/graph/expertise
  ?skill={str}&failure_mode={str}
  → {technicians: [{anon_id, skill_tags, relevant_procedures_count, work_order_count}]}
```

### Definition of Done
- [ ] 5 anonymized technicians in graph with skill tags derived from seeded work orders
- [ ] Query "hydraulic systems" returns 2–3 relevant technicians
- [ ] Privacy: zero names or personal identifiers in any API response or graph node

### Demo Scenario
"If a new failure occurs on a hydraulic pump, who has the right experience to handle it?" → search expertise → ranked results appear with skill confidence. "All anonymous by design — we preserve privacy while preserving institutional knowledge."

### Estimated AI-Assisted Development Time
**3–4 hours** — mostly extending existing graph patterns.

---

---

## Phase 9 — Knowledge Coverage Analytics

### Goal
Show what the system knows it doesn't know. Which equipment lacks SOPs? Which failure modes have no documented resolution? This creates urgency for further knowledge capture.

### User Value
"Your facility has 43 equipment nodes. 12 have no linked procedure. 7 have unresolved failure modes from the last 6 months."

### Features
- Coverage heatmap: equipment × knowledge dimension (SOP, maintenance procedure, failure history, recent observation)
- Orphan detection: failures with no resolution, equipment with no procedure
- Knowledge gap alerts: "Compressor-3 has had 4 failures in 6 months — no SOP linked"
- Coverage improvement tracking: % linked before/after ingesting a document

### Backend Tasks
1. Extend graph_service: `get_coverage_matrix(facility_id) → dict`
   - Per equipment: `{has_sop: bool, has_maintenance_proc: bool, has_failure_history: bool, has_recent_obs: bool}`
2. `GET /api/v1/graph/coverage` → coverage matrix
3. `GET /api/v1/graph/gaps` → equipment with specific gaps + recommendations

### Frontend Tasks
1. Coverage matrix table: rows = equipment, columns = knowledge dimensions, cells = green/red chips
2. Knowledge gap list with "Fix This" → navigates to ingest page with suggested document type

### Definition of Done
- [ ] Coverage matrix shows correct state for 10 seeded equipment
- [ ] At least 3 knowledge gaps surfaced with actionable descriptions

### Estimated AI-Assisted Development Time
**3 hours** — purely Cypher queries + table rendering.

---

---

## Phase 10 — Production Hardening

### Goal
Make the demo bulletproof. Every click should work. Loading states should be smooth. The system should recover gracefully from errors.

### Features
- ARQ task queue replacing BackgroundTasks (proper retry logic)
- Redis caching for all expensive queries
- Error boundary components in Next.js
- Loading skeletons on all data-fetch pages
- Demo mode seed script: one command resets to perfect demo state
- CLAUDE.md comprehensive enough to resume work in any session
- `make demo` script: starts all services, seeds data, opens browser

### Backend Tasks
1. Replace `BackgroundTasks` with ARQ workers (3 replicas)
2. Add Redis caching to all `graph_service` methods (5-min TTL on stable data)
3. Add circuit breaker pattern for Neo4j calls (if >3 failures in 10s → return cached/degraded)
4. `backend/scripts/reset_demo.sh` — wipes Neo4j + LanceDB, runs seed, verifies health
5. Comprehensive CLAUDE.md update with: architecture decisions, gotchas discovered, file map, test commands

### Frontend Tasks
1. `<ErrorBoundary>` wrapper around each major section
2. Loading skeletons (`@/components/ui/skeleton`) for all async components
3. `<Toast>` notifications for success/error states (shadcn/ui Toast)
4. Responsive design pass: looks good at 1280px (typical hackathon demo laptop)

### Definition of Done
- [ ] `make demo` works end-to-end: `make demo up && make demo seed && make demo health`
- [ ] All 7 demo scenarios from phases 0–9 work without errors
- [ ] No white screens on navigation to any page
- [ ] Error states (e.g., Ollama down) show user-friendly messages, not stack traces

### Estimated AI-Assisted Development Time
**4–5 hours**

---

---

## Recommended Folder Structure

```
foundry/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app, lifespan, router mounting
│   │   ├── core/
│   │   │   ├── config.py               # Settings (pydantic-settings, .env)
│   │   │   ├── security.py             # JWT: create_token, verify_token
│   │   │   └── deps.py                 # get_db, get_neo4j, get_current_user
│   │   ├── db/
│   │   │   ├── postgres.py             # SQLAlchemy async engine + session factory
│   │   │   ├── neo4j.py                # AsyncDriver singleton + context manager
│   │   │   └── lancedb.py              # LanceDB connect + table initialization
│   │   ├── models/
│   │   │   ├── orm/                    # SQLAlchemy models
│   │   │   │   ├── user.py
│   │   │   │   ├── document.py
│   │   │   │   ├── shift.py
│   │   │   │   └── copilot_session.py
│   │   │   └── schemas/                # Pydantic request/response schemas
│   │   │       ├── auth.py
│   │   │       ├── ingest.py
│   │   │       ├── copilot.py
│   │   │       ├── graph.py
│   │   │       ├── risk.py
│   │   │       └── shift.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── ingest.py
│   │   │   ├── copilot.py              # POST /query + WS /ws/copilot
│   │   │   ├── graph.py
│   │   │   ├── risk.py
│   │   │   ├── shift.py
│   │   │   └── admin.py
│   │   ├── agents/
│   │   │   ├── state.py                # FoundryState TypedDict
│   │   │   ├── graph_builder.py        # compile_ingestion_graph(), compile_query_graph()
│   │   │   └── nodes/
│   │   │       ├── supervisor.py       # route_by_input_type()
│   │   │       ├── document.py         # detect MIME, route to OCR or entity
│   │   │       ├── ocr.py              # PyMuPDF + Tesseract
│   │   │       ├── entity.py           # Qwen3 JSON extraction + retry
│   │   │       ├── entity_resolution.py# SHA256 ID + name dedup
│   │   │       ├── graph_write.py      # Neo4j MERGE all entities
│   │   │       ├── embedding.py        # chunk + embed → LanceDB
│   │   │       ├── retrieval.py        # GraphRAG: vector + graph + merge
│   │   │       ├── copilot.py          # Qwen3 streaming answer + citations
│   │   │       ├── voice.py            # Whisper → entity → observation
│   │   │       ├── shift.py            # multi-pass shift extraction
│   │   │       └── risk.py             # risk event scoring
│   │   └── services/
│   │       ├── ocr_service.py          # extract_text_pymupdf(), tesseract_fallback()
│   │       ├── whisper_service.py      # transcribe() using mlx-whisper
│   │       ├── embedding_service.py    # embed_chunks() via Ollama nomic-embed-text
│   │       ├── llm_service.py          # OllamaClient: generate(), stream(), embed()
│   │       ├── graph_service.py        # all Neo4j CRUD + traversal queries
│   │       └── risk_service.py         # scoring formulas
│   ├── workers/
│   │   ├── main.py                     # ARQ app definition
│   │   └── tasks.py                    # process_document_job(), process_voice_job()
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── scripts/
│   │   ├── seed_data.py                # create Nexus factory seed data
│   │   ├── init_neo4j.py               # create all constraints + indexes
│   │   ├── reset_demo.sh               # wipe + re-seed for clean demo state
│   │   └── load_models.sh              # ollama pull qwen3:8b-q4_K_M nomic-embed-text
│   ├── tests/
│   │   ├── test_entity_extraction.py
│   │   ├── test_graphrag_retrieval.py
│   │   └── test_shift_pipeline.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── CLAUDE.md
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                # redirect to /dashboard
│   │   │   ├── login/page.tsx
│   │   │   └── dashboard/
│   │   │       ├── layout.tsx          # Sidebar + TopBar wrapper
│   │   │       ├── page.tsx            # Overview dashboard
│   │   │       ├── copilot/page.tsx
│   │   │       ├── graph/
│   │   │       │   ├── page.tsx        # Graph explorer
│   │   │       │   └── [id]/page.tsx   # Equipment detail
│   │   │       ├── ingest/page.tsx
│   │   │       ├── shift/
│   │   │       │   ├── page.tsx        # Shift history
│   │   │       │   └── new/page.tsx    # New shift handover
│   │   │       └── risk/page.tsx
│   │   ├── components/
│   │   │   ├── ui/                     # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── TopBar.tsx
│   │   │   ├── copilot/
│   │   │   │   ├── ChatInterface.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── SourcePanel.tsx
│   │   │   ├── graph/
│   │   │   │   ├── GraphCanvas.tsx     # Cytoscape.js wrapper
│   │   │   │   ├── EntitySidebar.tsx   # slide-in on node click
│   │   │   │   └── FailureTimeline.tsx
│   │   │   ├── ingest/
│   │   │   │   ├── DropZone.tsx
│   │   │   │   ├── ProgressTracker.tsx
│   │   │   │   ├── EntityPreview.tsx
│   │   │   │   └── VoiceUploader.tsx
│   │   │   ├── shift/
│   │   │   │   ├── ShiftEditor.tsx
│   │   │   │   └── SummaryView.tsx
│   │   │   ├── risk/
│   │   │   │   ├── HeatmapZones.tsx    # SVG facility map
│   │   │   │   └── RiskCard.tsx
│   │   │   └── dashboard/
│   │   │       ├── StatCard.tsx
│   │   │       ├── ActivityFeed.tsx
│   │   │       └── EquipmentGrid.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                  # Axios with JWT interceptor
│   │   │   └── ws.ts                   # WebSocket wrapper with reconnect
│   │   ├── stores/
│   │   │   ├── auth.ts                 # Zustand: user, token, role
│   │   │   ├── copilot.ts              # messages, sessionId, isStreaming
│   │   │   └── graph.ts                # selectedNode, filterTypes
│   │   └── types/index.ts              # all shared TypeScript interfaces
│   ├── public/
│   │   └── facility-zones.json         # hardcoded Nexus Plant zone SVG polygons
│   ├── Dockerfile
│   ├── package.json
│   └── next.config.js
├── docker-compose.yml
├── docker-compose.override.yml         # dev: hot-reload volume mounts
├── Makefile                            # make dev, make seed, make demo, make reset
├── .env.example
├── CLAUDE.md                           # project-level context for AI sessions
└── README.md
```

---

## Development Order: File-by-File Implementation Sequence

### Week 1 — Foundation + Ingestion (Phases 0–1)
```
Day 1  docker-compose.yml
       .env.example
       CLAUDE.md (project-level)
       backend/requirements.txt
       backend/app/core/config.py

Day 2  backend/app/db/postgres.py
       backend/app/db/neo4j.py
       backend/app/db/lancedb.py
       backend/alembic/env.py + 001_initial.py
       backend/scripts/init_neo4j.py

Day 3  backend/app/models/orm/*.py (all 4 models)
       backend/app/models/schemas/*.py (all 6 schema files)
       backend/app/core/security.py + deps.py
       backend/app/routers/auth.py
       backend/app/main.py

Day 4  frontend/package.json + next.config.js
       frontend/src/app/layout.tsx
       frontend/src/app/login/page.tsx
       frontend/src/stores/auth.ts
       frontend/src/lib/api.ts
       frontend/src/app/dashboard/layout.tsx (sidebar nav skeleton)

Day 5  backend/app/services/llm_service.py
       backend/app/services/ocr_service.py
       backend/app/services/embedding_service.py
       backend/app/agents/state.py

Day 6  backend/app/agents/nodes/entity.py
       backend/app/agents/nodes/embedding.py
       backend/workers/tasks.py (BackgroundTasks version)
       backend/app/routers/ingest.py

Day 7  frontend/src/components/ingest/DropZone.tsx
       frontend/src/components/ingest/ProgressTracker.tsx
       frontend/src/components/ingest/EntityPreview.tsx
       frontend/src/app/dashboard/ingest/page.tsx
       backend/scripts/seed_data.py
       ** MILESTONE: Upload PDF → see entities extracted **
```

### Week 2 — Graph + Copilot (Phases 2–3)
```
Day 8  backend/app/agents/nodes/entity_resolution.py
       backend/app/agents/nodes/graph_write.py
       backend/app/services/graph_service.py (CRUD methods)
       backend/app/agents/graph_builder.py (ingestion graph compiled)

Day 9  backend/app/routers/graph.py
       frontend/src/components/graph/GraphCanvas.tsx
       frontend/src/components/graph/EntitySidebar.tsx
       frontend/src/stores/graph.ts

Day 10 frontend/src/app/dashboard/graph/page.tsx
       frontend/src/app/dashboard/graph/[id]/page.tsx
       frontend/src/components/graph/FailureTimeline.tsx
       ** MILESTONE: Graph renders; click node sees history **

Day 11 backend/app/agents/nodes/retrieval.py  (hardest file — take your time)
       backend/app/agents/nodes/copilot.py
       backend/app/agents/graph_builder.py (add query graph)

Day 12 backend/app/routers/copilot.py (POST + WebSocket)
       frontend/src/lib/ws.ts
       frontend/src/stores/copilot.ts
       frontend/src/components/copilot/ChatInterface.tsx
       frontend/src/components/copilot/MessageBubble.tsx

Day 13 frontend/src/components/copilot/SourcePanel.tsx
       frontend/src/app/dashboard/copilot/page.tsx
       ** MILESTONE: Ask Copilot question → streaming answer with citations **

Day 14 BUFFER: Debug retrieval quality, tune entity extraction prompt
```

### Week 3 — Voice + Shift + Dashboard (Phases 4–6)
```
Day 15 backend/app/services/whisper_service.py
       backend/app/agents/nodes/voice.py
       frontend/src/components/ingest/VoiceUploader.tsx
       ** MILESTONE: Upload voice note → Observation in graph **

Day 16 backend/app/agents/nodes/shift.py
       backend/app/routers/shift.py
       frontend/src/components/shift/ShiftEditor.tsx
       frontend/src/components/shift/SummaryView.tsx

Day 17 frontend/src/app/dashboard/shift/new/page.tsx
       frontend/src/app/dashboard/shift/page.tsx
       ** MILESTONE: Submit shift note → structured summary **

Day 18 backend/app/routers/admin.py (health + stats)
       frontend/src/components/dashboard/StatCard.tsx
       frontend/src/components/dashboard/ActivityFeed.tsx
       frontend/src/components/dashboard/EquipmentGrid.tsx
       frontend/src/app/dashboard/page.tsx
       ** MILESTONE: Dashboard fully populated **

Day 19 backend/app/services/risk_service.py
       backend/app/routers/risk.py
       frontend/src/components/risk/HeatmapZones.tsx
       public/facility-zones.json
       frontend/src/app/dashboard/risk/page.tsx
       ** MILESTONE: Risk heatmap with red zones visible **

Day 20 backend/scripts/reset_demo.sh
       Makefile (dev, seed, demo, reset targets)
       backend/CLAUDE.md (comprehensive update)
       Polish: loading skeletons, error boundaries, toast notifications
       ** MILESTONE: Full demo flow works end-to-end **
```

---

## What Can Be Mocked For Demo

These items require ZERO real implementation but create demo realism:

| Item | Mock Strategy |
|---|---|
| Factory floor plan | Invent a 5-zone SVG polygon layout; hardcode in `facility-zones.json` |
| Risk heatmap zones | Pre-seed Neo4j with RiskEvent nodes calibrated to make Area A red, Area B yellow |
| Work order history | CSV import of 20 fabricated work orders — no ERP integration needed |
| Shift history | 3 pre-seeded shifts in Postgres so history list isn't empty |
| Real equipment names | "Pump-7", "Compressor-3", "Hydraulic Press-2" — sound industrial, need no verification |
| Voice demo audio | Record yourself saying maintenance observations before the demo; use pre-recorded file |
| Real OCR scanned docs | All demo PDFs should be text-layer (created with Word → PDF); skip scanned SOP demo |
| BGE Reranker | Use pure score-based top-K selection; nobody will notice the missing 10% recall improvement |
| Technician expertise | 5 anonymized technician nodes with hardcoded skill tags; linked to seeded work orders |
| Multi-shift continuity | Manually create 3 shifts that reference the same equipment to show "patterns over time" |
| CMMS integration | "Our platform ingests CMMS exports in CSV format" — show CSV upload instead of live API |
| Risk trend detection | Pre-seed with 6 events over 30 days for Pump-7; trend naturally comes out as "worsening" |
| PII scrubbing demo | Include a technician name in a sample shift note; show it gets stripped in the output |
| Air-gap deployment | "Designed for Jetson AGX Orin deployment — fully offline" → mention in pitch, skip live demo |
| Advanced analytics | Coverage matrix can use hardcoded % for MVP ("43% coverage" looks impressive) |

---

## Biggest Technical Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Qwen3 entity extraction returns malformed JSON** | High (happens ~15% of prompts) | High (blocks graph write) | Add strict retry with error-correction prompt; validate schema with Pydantic; fallback to partial extraction |
| 2 | **WebSocket streaming unstable under rapid token delivery** | Medium | High (demo breaks mid-sentence) | Implement token batching (flush every 3 tokens); handle reconnect in `ws.ts`; test with long responses |
| 3 | **Neo4j entity resolution creates duplicate nodes** | High (different capitalization, aliases) | Medium (messy graph, wrong Copilot answers) | Normalize all names to `lower().strip()` before MERGE; add `toLower()` to Cypher MATCH; test with your seed documents |
| 4 | **Copilot returns hallucinated answers** | Medium | High (catastrophic for demo credibility) | Strict system prompt: "If the context does not contain the answer, say exactly: I don't have documented information about that." Test 20 queries before demo |
| 5 | **mlx-whisper / Whisper setup failure on M4** | Low-Medium | High (kills voice demo) | Test `openai-whisper` as fallback; pre-transcribe demo audio and hardcode transcript if needed |
| 6 | **LanceDB vector search returns irrelevant results** | Medium | High (Copilot answers are useless) | Use cosine similarity threshold filter (score > 0.5); ensure seed documents contain specific equipment names matching your demo queries exactly |
| 7 | **Cytoscape.js graph rendering slow with >100 nodes** | Medium | Medium (visual demo looks bad) | Limit initial render to 50 nodes; use `cose-bilkent` layout with `animate: false`; add "Load More" pagination |
| 8 | **Ollama slow first token (cold model)** | Low (keep-alive set) | High (demo awkward pause) | Set `OLLAMA_KEEP_ALIVE=24h`; make a warmup request during startup health check; demo from a warm state |
| 9 | **Demo data state corruption** | Medium | High (demo breaks) | `make reset` + `make seed` takes <2 minutes; run it before every serious demo; keep seed script idempotent |
| 10 | **LangGraph state persistence bug (SQLite)** | Low | Medium | Use SQLiteSaver but clear checkpoint DB in `reset_demo.sh`; if bugs appear, set `checkpointer=None` for MVP |

---

## Fastest Path to a Winning Hackathon Demo

**If you only have 3 weeks:** Complete Phases 0–5 + risk heatmap (Phase 7 partial). Skip Phases 8, 9, 10 entirely.

**The minimum winning demo is:**

```
1. Dashboard  →  shows seeded factory data; looks like a real operations center
2. Upload SOP →  watch entity extraction in real-time; see graph update
3. Copilot    →  "What resolved the last Pump-7 failure?" → streaming answer with citations
4. Voice note →  record 20-second observation; watch it link to graph
5. Shift note →  paste messy text; get structured handover report
6. Risk map   →  Area A is red; click it; "Pump-7 critical, 6 failures this month"
```

**That demo answers the three judge questions that matter:**

> *"What problem does this solve?"* — Industrial facilities lose decades of knowledge when experienced workers leave. Foundry converts it into a permanent, queryable intelligence layer.

> *"Is the tech sophisticated?"* — Yes: GraphRAG (not naive RAG), voice transcription, graph-first data model, privacy-by-architecture, real-time streaming.

> *"Does it work?"* — Yes. Live demo. All 6 flows run without errors.

**Elapsed time to this demo: ~50–55 hours of AI-assisted development.**

**What makes it *win* rather than just work:**
- The streaming Copilot response is viscerally impressive — token by token, with citations appearing
- The graph visualization with failure relationship chains is visually distinctive
- The voice → structured observation flow takes 30 seconds and looks magical
- The shift note → structured handover with risk flags is immediately relatable to anyone who's been in operations
- The risk heatmap looks like the products facility managers actually use (Ignition, AVEVA) but smarter

Ship Phases 0–5 first. Add Phase 7 heatmap last. Everything else is a bonus.

---

*Total estimated AI-assisted development time: 55–65 hours (Phases 0–7). With strong seed data and a rehearsed demo script, this competes with any team regardless of size.*