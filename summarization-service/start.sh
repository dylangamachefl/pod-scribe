#!/bin/sh
# Startup script for Summarization service
# Runs both the FastAPI application and the event subscriber

# Start FastAPI application in foreground
echo "Starting FastAPI application (Event Subscriber managed by lifespan)..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8002
