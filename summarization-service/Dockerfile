FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY summarization-service/pyproject.toml ./
COPY summarization-service/src/ ./src/
COPY summarization-service/config/ ./config/
COPY summarization-service/start.sh ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Install Redis client for events
RUN pip install --no-cache-dir redis

# Make startup script executable
RUN chmod +x start.sh

# Set PYTHONPATH so imports work correctly (including events from /app/shared mounted at runtime)
ENV PYTHONPATH=/app/src:/app/shared

# Expose port
EXPOSE 8002

# Run both API and event subscriber via startup script
CMD ["./start.sh"]
