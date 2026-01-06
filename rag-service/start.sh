#!/bin/sh
# Startup script for RAG service
# Runs both the FastAPI application and the event subscriber

echo "Starting RAG Service with Event Subscriber..."

# Start FastAPI application in foreground
# Event subscriber is started automatically by lifespan manager in main.py
echo "Starting FastAPI application..."
uvicorn src.main:app --host 0.0.0.0 --port 8000
