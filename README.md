# FOUNDRY

**Industrial Memory & Operational Intelligence Platform**

## Overview
Foundry is an AI-powered industrial intelligence platform designed for manufacturing plants. It extracts, organizes, and retrieves operational knowledge from unstructured documents (SOPs, Work Orders, Incident Reports, Voice Notes) into a structured Knowledge Graph.

By persisting institutional knowledge rather than relying on ephemeral search, Foundry ensures that relationships between equipment, failure modes, and resolution procedures survive across shifts and system restarts.

## Key Features
- **Knowledge Ingestion Core**: Real-time extraction of entities (Equipment, Procedures, Failures) from PDFs and text using OCR and LLMs.
- **Knowledge Graph Foundation**: Neo4j-backed graph database connecting equipment failure history, procedures, and operational observations.
- **Foundry Copilot**: A hybrid GraphRAG conversational agent that answers engineering queries grounded in specific facility documentation with inline citations.
- **Risk & Shift Intelligence**: Automated processing of unstructured shift notes into structured summaries, alongside visual risk heatmaps to detect recurring failure patterns.

## Tech Stack
- **Backend**: FastAPI, Python 3.11, LangGraph (Multi-Agent framework), SQLAlchemy (PostgreSQL), Neo4j, LanceDB
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui, Cytoscape.js
- **AI Models**: Qwen2.5 (via Ollama), Nomic Embed Text, PaddleOCR, Whisper (Voice processing)
- **Infrastructure**: Docker Compose, Redis (Task queues)

## Getting Started

### Prerequisites
- Docker Desktop
- Node.js 20+
- Python 3.11+

### Running the System
The system is designed to run locally using Docker Compose to orchestrate the databases and AI models.

1. **Start Infrastructure Services**:
   ```bash
   docker compose up -d
   ```
   *This starts PostgreSQL, Neo4j, Redis, and Ollama.*

2. **Pull Required AI Models**:
   ```bash
   docker compose exec ollama ollama pull qwen2.5
   docker compose exec ollama ollama pull nomic-embed-text
   ```

3. **Start the Backend**:
   Navigate to the `backend/` directory, set up your Python environment, and run the FastAPI server:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Start the Frontend**:
   Navigate to the `frontend/` directory, install dependencies, and run the Next.js server:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

The application will be available at `http://localhost:3000`.

## Architecture
The system employs an **Edge-First, Offline-by-Design** architecture suitable for air-gapped deployments on devices like the NVIDIA Jetson AGX Orin or modern M-series MacBooks. All inference, storage, and retrieval are colocated without outbound network dependencies.
