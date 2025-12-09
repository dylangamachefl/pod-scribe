# ================================================================
# Multi-stage Dockerfile for React + Vite Frontend
# ================================================================

# Stage 1: Build the application
FROM node:20-alpine AS builder

# Accept build arguments for environment variables
ARG VITE_USE_MOCK_API=false
ARG VITE_RAG_API_URL=http://localhost:8000
ARG VITE_TRANSCRIPTION_API_URL=http://localhost:8001
ARG VITE_SUMMARIZATION_API_URL=http://localhost:8002

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Create .env file from build args (Vite needs these at build time)
RUN echo "VITE_USE_MOCK_API=${VITE_USE_MOCK_API}" > .env && \
    echo "VITE_RAG_API_URL=${VITE_RAG_API_URL}" >> .env && \
    echo "VITE_TRANSCRIPTION_API_URL=${VITE_TRANSCRIPTION_API_URL}" >> .env && \
    echo "VITE_SUMMARIZATION_API_URL=${VITE_SUMMARIZATION_API_URL}" >> .env

# Build the application
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 3000 (to match docker-compose configuration)
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
