
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
