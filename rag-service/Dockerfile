FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY rag-service/pyproject.toml ./
COPY rag-service/src/ ./src/
COPY rag-service/start.sh ./

# Optimize build cache: Install shared package dependencies first
COPY shared/pyproject.toml /tmp/shared/
RUN pip install --no-cache-dir redis pydantic sqlalchemy[asyncio] asyncpg alembic python-dotenv

# Copy shared package source and install
COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir -e /tmp/shared && \
    pip install --no-cache-dir -e .

# Install Redis client for events
RUN pip install --no-cache-dir redis

# Make startup script executable
RUN chmod +x start.sh

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run FastAPI application (event subscriber starts automatically in lifespan)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
