# Contributing to Podcast Transcriber

Thank you for your interest in contributing! This guide will help you get started with development.

## 📋 Table of Contents

- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Git Workflow](#git-workflow)
- [Testing](#testing)
- [Adding New Services](#adding-new-services)
- [Debugging Tips](#debugging-tips)

---

## 🚀 Development Setup

### Prerequisites

- **Docker Desktop** (required for all services)
- **Python 3.11+** (for local development)
- **Node.js 18+** (for frontend development)
- **Ollama** (for RAG/chat features)
- **NVIDIA GPU** (optional, for GPU-accelerated transcription)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dylangamachefl/pod-scribe.git
   cd pod-scribe
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. **Setup Ollama models:**
   ```bash
   ollama pull qwen3:8b
   ollama pull nomic-embed-text
   ollama create qwen3:rag -f models/Modelfile_rag
   ollama create qwen3:summarizer -f models/Modelfile_sum
   ```

4. **Start the application:**
   ```bash
   # Windows
   start_app.bat
   
   # Linux/Mac
   docker-compose up -d
   ```

### Service-Specific Development

#### Backend Services (Python)

Each service has its own virtual environment for local development:

```bash
# Example: RAG Service
cd rag-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

---

## 📝 Code Style Guidelines

### Python

- **Style Guide:** Follow [PEP 8](https://pep8.org/)
- **Type Hints:** Use type hints for all function signatures
- **Docstrings:** Use Google-style docstrings for classes and functions
- **Formatting:** Use `black` for code formatting (line length: 100)
- **Linting:** Use `ruff` for linting

**Example:**
```python
from typing import List, Optional

def process_transcript(
    episode_id: str,
    chunks: List[dict],
    max_tokens: Optional[int] = None
) -> dict:
    """Process transcript chunks for an episode.
    
    Args:
        episode_id: Unique identifier for the episode
        chunks: List of transcript chunks with text and timestamps
        max_tokens: Optional maximum token limit for processing
        
    Returns:
        Dictionary containing processed transcript data
        
    Raises:
        ValueError: If episode_id is invalid
    """
    # Implementation here
    pass
```

### JavaScript/React

- **Style Guide:** Follow [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- **Formatting:** Use Prettier (configured in `.prettierrc`)
- **Linting:** Use ESLint (configured in `.eslintrc`)
- **Components:** Use functional components with hooks
- **File Naming:** Use PascalCase for components, camelCase for utilities

### Docker

- **Multi-stage builds:** Use multi-stage builds to minimize image size
- **Layer caching:** Order Dockerfile commands to maximize layer caching
- **Security:** Don't include secrets in images; use Docker secrets or environment variables

---

## 🔀 Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions/updates

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**
```
feat(rag): add hybrid search with BM25 and vector similarity

Implemented Reciprocal Rank Fusion (RRF) to combine BM25 keyword 
search with Qdrant vector similarity search for improved retrieval.

Closes #42
```

### Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** following code style guidelines
3. **Write/update tests** for your changes
4. **Update documentation** as needed
5. **Ensure all tests pass** locally
6. **Create a pull request** with a clear description
7. **Address review feedback** promptly

---

## 🧪 Testing

### Running Tests

```bash
# Python services (example: RAG service)
cd rag-service
pytest tests/ -v

# Frontend
cd frontend
npm test
```

### Writing Tests

- **Unit tests:** Test individual functions and classes
- **Integration tests:** Test service interactions
- **End-to-end tests:** Test complete workflows

**Example Python test:**
```python
import pytest
from services.hybrid_retriever import HybridRetriever

def test_hybrid_search():
    """Test hybrid search returns relevant results."""
    retriever = HybridRetriever()
    results = retriever.search(
        query="machine learning",
        episode_id="test-123",
        limit=5
    )
    
    assert len(results) <= 5
    assert all("score" in r for r in results)
    assert all("text" in r for r in results)
```

### Test Coverage

- Aim for **80%+ code coverage** for new code
- Run coverage reports: `pytest --cov=src tests/`

---

## 🏗️ Adding New Services

To add a new microservice to the monorepo:

1. **Create service directory:**
   ```bash
   mkdir new-service
   cd new-service
   ```

2. **Create standard structure:**
   ```
   new-service/
   ├── src/
   │   ├── __init__.py
   │   ├── main.py          # FastAPI app
   │   ├── config.py        # Configuration
   │   ├── models.py        # Data models
   │   └── services/        # Business logic
   ├── tests/
   ├── Dockerfile
   ├── requirements.txt
   └── README.md
   ```

3. **Add to docker-compose.yml:**
   ```yaml
   new-service:
     build:
       context: .
       dockerfile: new-service/Dockerfile
     environment:
       - DATABASE_URL=${DATABASE_URL}
     depends_on:
       - postgres
       - redis
   ```

4. **Use shared components:**
   ```python
   from podcast_transcriber_shared.database import get_db_connection
   from podcast_transcriber_shared.events import EventBus
   ```

5. **Document the service:**
   - Add comprehensive README.md
   - Update main project README
   - Add API documentation

---

## 🐛 Debugging Tips

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rag-service

# Transcription worker
docker-compose logs -f transcription-worker
```

### Debugging Python Services

1. **Add breakpoints:**
   ```python
   import pdb; pdb.set_trace()
   ```

2. **Run service locally** (outside Docker):
   ```bash
   cd rag-service
   source venv/bin/activate
   python -m uvicorn src.main:app --reload --port 8000
   ```

3. **Use VS Code debugger:**
   - Set breakpoints in VS Code
   - Use "Python: FastAPI" debug configuration

### Common Issues

**Docker build fails:**
- Clear Docker cache: `docker-compose build --no-cache`
- Check disk space: `docker system df`

**Database connection errors:**
- Verify PostgreSQL is running: `docker-compose ps postgres`
- Check connection string in `.env`

**GPU not detected:**
- Verify NVIDIA Docker runtime: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
- Check Docker Desktop GPU settings

**Port conflicts:**
- Check what's using the port: `netstat -ano | findstr :8000` (Windows)
- Update port mapping in `docker-compose.yml`

---

## 📚 Additional Resources

- [Project Architecture](ARCHITECTURE.md)
- [API Documentation](docs/api_endpoints.md)
- [Event Bus Architecture](docs/architecture/event_bus.md)
- [GPU Setup Guide](GPU_SETUP.md)

---

## 🤝 Getting Help

- **Issues:** Open an issue on GitHub
- **Discussions:** Use GitHub Discussions for questions
- **Documentation:** Check the `docs/` directory

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.
