# FOUNDRY

## Project Context
Foundry is an Industrial Memory Platform designed to capture, structure, and query domain knowledge for heavy industries (manufacturing, energy, logistics). It replaces fragmented documentation with an active knowledge graph that assists technicians and engineers on the floor.

## Architecture
- **Backend:** FastAPI, Python 3.11+
- **Frontend:** Next.js 14+ (App Router), React, Tailwind, shadcn/ui
- **Postgres:** Canonical storage for users, shifts, audit logs.
- **Neo4j:** The main Knowledge Graph mapping equipment, components, failure modes, procedures.
- **LanceDB:** Embedded vector store for semantic search over unstructured text.
- **Ollama:** Local LLM provider for zero-cost RAG and entity extraction.
- **Redis:** Message broker for background workers (arq).

## Coding Conventions
- **Python:** Strict type hints (`-> list[str]`), modern async/await patterns, SQLAlchemy 2.0 paradigms, explicit exception handling.
- **TypeScript:** Strict typing, prefer interfaces over types for object shapes, use React Server Components where possible, client components for interactivity (`"use client"`).
- **Styling:** Tailwind CSS, mobile-first responsive design, dark mode default.

## Key Instructions
- When making schema changes, always generate or update Alembic migrations.
- When creating Neo4j queries, use parameterized Cypher.
- Follow the Hackathon MVP roadmap. Do not add unnecessary features. Keep it simple, maintainable, and demo-focused.
