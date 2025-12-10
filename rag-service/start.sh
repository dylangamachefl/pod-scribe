#!/bin/sh
# Startup script for RAG service
# Runs both the FastAPI application and the event subscriber

echo "Starting RAG Service with Event Subscriber..."

# Start event subscriber in background
echo "Starting event subscriber..."
python src/event_subscriber.py &
SUBSCRIBER_PID=$!
echo "Event subscriber started (PID: $SUBSCRIBER_PID)"

# Wait a moment for subscriber to initialize
sleep 2

# Start FastAPI application in foreground
echo "Starting FastAPI application..."
uvicorn src.main:app --host 0.0.0.0 --port 8000

# If FastAPI exits, kill subscriber
kill $SUBSCRIBER_PID 2>/dev/null
