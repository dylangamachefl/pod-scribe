# Codebase Refactoring Task

## Phase 1: Project Structure & Packaging
- [/] Create `pyproject.toml` for shared module packaging
- [ ] Remove all `sys.path.insert()` hacks
  - [ ] `summarization-service/src/event_subscriber.py`
  - [ ] `summarization-service/process_existing.py`
  - [ ] `transcription-service/test_feed.py`
  - [ ] `transcription-service/src/api/transcription_api.py`
  - [ ] `transcription-service/src/worker_daemon.py`
  - [ ] `transcription-service/src/core/processor.py`
  - [ ] `rag-service/build_indexes.py`
  - [ ] `rag-service/src/event_subscriber.py`
  - [ ] `shared/config/test_dedup.py`
  - [ ] `shared/config/debug_feed.py`
- [ ] Update imports across services to use installed package
- [ ] Update Docker files to install shared package

## Phase 2: Transcription Service Optimization
- [ ] Create `TranscriptionWorker` class in `audio.py`
  - [ ] Add persistent model loading in `__init__`
  - [ ] Create `process(audio_path)` method
  - [ ] Add proper exception handling
- [ ] Update `processor.py` to use `TranscriptionWorker`
- [ ] Add `diarization_failed` flag to metadata
  - [ ] Modify diarization fallback logic
  - [ ] Update event publishing to include flag
- [ ] Update shared events.py to include diarization_failed field

## Phase 3: RAG Service & Search Stability
- [ ] Fix BM25 O(N) memory usage in `hybrid_retriever.py`
  - [ ] Remove in-memory document list
  - [ ] Implement Qdrant sparse vector support
  - [ ] Update ranking logic
- [ ] Externalize prompts in summarization service
  - [ ] Create `config/prompts.yaml`
  - [ ] Refactor `gemini_service.py` to load from YAML
  - [ ] Move all hardcoded prompts to config file

## Phase 4: Workflow Logic
- [ ] Remove file watcher from `summarization-service`
  - [ ] Delete file watcher code
  - [ ] Update service to rely solely on event bus
  - [ ] Update startup scripts
  - [ ] Verify event subscriber is the only trigger

## Phase 5: Code Quality Improvements
- [ ] Add type hints to all refactored functions
- [ ] Replace generic exception handlers with specific ones
- [ ] Improve logging standards
- [ ] Update documentation
