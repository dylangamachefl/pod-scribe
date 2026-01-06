# Architectural Review & DevSecOps Analysis

## 1. Resource Management & Bottlenecks

### Critical: VRAM Collision (WhisperX vs. Ollama)
**Severity:** 🔥 Critical (System Crash Risk)

- **Issue:** The `transcription-worker` container loads Whisper Large-v2 (~4-6GB VRAM) into the GPU. The `rag-service` connects to `host.docker.internal:11434`, utilizing Ollama on the host machine.
- **Constraint:** The system runs on an RTX 3070 with an **8GB VRAM limit**.
- **Impact:** If a transcription job runs simultaneously with a RAG query (or ingestion), the combined VRAM usage (~5GB + ~5GB) will exceed 8GB, causing an Out-Of-Memory (OOM) crash for one or both processes.
- **Recommendation:**
  - Implement a **Distributed Lock (Mutex)** using Redis.
  - Before loading heavy models or executing inference, services must acquire a `gpu_lock`.
  - Example: `rag-service` must wait for `transcription-worker` to release the lock, and vice-versa.

---

## 2. Event-Driven Reliability

### Critical: "At Most Once" Delivery (Data Loss Risk)
**Severity:** 🔴 High

- **Issue:** In `shared/podcast_transcriber_shared/events.py`, the `subscribe` method uses `xreadgroup` followed by `xack`. Inside the processing loop (`_process_entry`), exceptions are caught and printed.
- **Impact:** If processing fails (e.g., database error), the exception is suppressed, and the code proceeds to `xack` (acknowledge) the message. This tells Redis the message was successfully processed, removing it from the Pending Entries List (PEL). The message is **permanently lost**.
- **Recommendation:**
  - Only call `xack` **after** successful processing.
  - If processing fails, **do not ACK**. Let the message expire or remain in PEL.
  - Implement a **Dead Letter Queue (DLQ)** mechanism: check `delivery_count` and move permanently failing messages to a separate stream for manual inspection.

### Reliability: Transcription Queue Implementation
**Severity:** 🟠 Medium

- **Issue:** The `transcription-worker` uses `blpop` (Redis List) in `worker_daemon.py`.
- **Impact:** `blpop` removes the item from the queue immediately upon retrieval. If the worker crashes mid-process (e.g., power failure), the job is lost.
- **Recommendation:**
  - Migrate transcription jobs to **Redis Streams** (like the RAG service) or use `rpoplpush` (reliable queue pattern) to keep the job in a "processing" list until completion.

### Architecture: Double Consumer Issue
**Severity:** 🟠 Medium

- **Issue:** The `rag-service` starts the event subscriber in two places:
  1. `start.sh` launches `python src/event_subscriber.py &`
  2. `src/main.py` launches `start_rag_event_subscriber()` as a background task in `lifespan`.
- **Impact:** Two consumer instances run simultaneously. While Redis Consumer Groups handle load balancing, this is redundant, wasteful, and can lead to race conditions or confusing logs.
- **Recommendation:** Remove the background process in `start.sh` and rely solely on the `lifespan` manager in `main.py` for better lifecycle control.

---

## 3. Monorepo "Smells"

### Dependency Management
**Status:** ✅ Clean
- **Analysis:** `transcription-api` builds from `Dockerfile.api` and imports `podcast_transcriber_shared`. The shared library contains lightweight dependencies (SQLAlchemy, Pydantic, Redis). The heavy ML libraries (Torch, WhisperX) are isolated in the `transcription-worker`.

### Dockerfile Optimization
**Severity:** 🟡 Low (Build Time)

- **Issue:** `rag-service/Dockerfile` copies the entire `shared/` directory (`COPY shared/ /tmp/shared/`) before installing dependencies.
- **Impact:** Any change to *any* file in `shared/` (even a comment) invalidates the Docker cache for the `pip install` step, forcing a slow rebuild of dependencies.
- **Recommendation:**
  - Copy `shared/pyproject.toml` first, install dependencies, and *then* copy the source code.

---

## 4. Data & Security Integrity

### Security: Secrets Management Inconsistency
**Severity:** 🟠 Medium

- **Issue:**
  - `summarization-service` correctly uses Docker Secrets for `gemini_api_key`.
  - `transcription-worker` injects `HUGGINGFACE_TOKEN` via a plain environment variable in `docker-compose.yml`.
- **Impact:** Environment variables can be leaked in logs or `docker inspect`.
- **Recommendation:** Move `HUGGINGFACE_TOKEN` to Docker Secrets, consistent with the Gemini key.

### Data: Shared File System Usage
**Status:** ⚠️ Mixed
- **Analysis:** The `rag-service` configuration references `TRANSCRIPTION_WATCH_PATH` (shared volume), but the core logic (`process_summary_event`) retrieves transcripts from PostgreSQL.
- **Verdict:** The system has correctly moved towards Database-as-Source-of-Truth. Ensure all legacy file-system dependencies are removed to allow services to run on different nodes if needed.

---

## 5. RAG Best Practices

### Context Window Under-utilization
**Severity:** 🟡 Optimization

- **Issue:** `rag-service` uses `CHUNK_SIZE=500` characters (~100-120 tokens).
- **Context:** The model is `qwen3:rag` (likely Qwen 2.5 based), which supports at least 8k context (and up to 32k/128k). The prompt mentions a 6144 window.
- **Impact:** 500 characters is too short to capture meaningful context or coherent thoughts in a podcast. Retrieving 5 chunks results in only ~600 tokens of context, wasting ~90% of the available window.
- **Recommendation:**
  - Increase `CHUNK_SIZE` to **1500-2000 characters**.
  - Increase overlap to ensure continuity.
  - This provides the LLM with richer context for answering queries.
