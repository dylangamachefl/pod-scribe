FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY pyproject.toml ./
COPY src/ ./src/
COPY start.sh ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Install Redis client for events
RUN pip install --no-cache-dir redis

# Make startup script executable
RUN chmod +x start.sh

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8002

# Run both API and event subscriber via startup script
CMD ["./start.sh"]
