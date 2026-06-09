#!/usr/bin/env bash

# Wait for ollama to be ready
echo "Waiting for Ollama to be available..."
while ! curl -s http://localhost:11434/api/tags > /dev/null; do
  sleep 1
done

echo "Ollama is up. Pulling models..."
curl -X POST http://localhost:11434/api/pull -d '{"name": "qwen3:8b-q4_K_M"}'
curl -X POST http://localhost:11434/api/pull -d '{"name": "nomic-embed-text"}'
echo "Models pulled successfully."
