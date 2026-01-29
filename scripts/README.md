# Scripts Directory

Utility scripts for managing, debugging, and maintaining the podcast transcription system.

## 📁 Directory Structure

```
scripts/
├── host_listener.py          # HTTP service for triggering Docker transcription
├── start_listener.bat        # Windows launcher for host listener
├── run_bot.bat              # Legacy launcher (deprecated)
├── init_database.py         # Database initialization utility
├── migrate_feeds_and_queue.py # Database migration script
├── reset_stuck_jobs.py      # Debug utility for stuck transcription jobs
├── test_events.py           # Event system testing utility
└── debug_status.py          # Pipeline status debugging tool
```

---

## 🚀 Primary Scripts

### `host_listener.py`

**Purpose:** HTTP service that runs on your Windows host machine to trigger Docker transcription workers.

**Architecture:**
```
UI Button (localhost:3000) 
  ↓
Transcription API (Docker container on port 8001)
  ↓  
Host Listener Service (localhost:8080)
  ↓
docker-compose run transcription-worker
```

**Usage:**
```bash
# Option 1: Using batch script (Recommended)
scripts\start_listener.bat

# Option 2: Direct execution
cd scripts
python host_listener.py
```

**Endpoints:**
- `GET /health` - Health check
- `POST /start` - Start transcription worker
- `GET /status` - Get listener status

**Requirements:**
- Python 3.7+
- Flask, flask-cors
- Docker Desktop running

**Troubleshooting:**
- Ensure port 8080 is available
- Verify Docker Desktop is running
- Check http://localhost:8080/health for status

---

### `init_database.py`

**Purpose:** Initialize the PostgreSQL database schema for all services.

**Usage:**
```bash
python scripts\init_database.py
```

**What it does:**
- Creates database tables for transcription, RAG, and summarization services
- Sets up indexes and constraints
- Safe to run multiple times (idempotent)

---

### `migrate_feeds_and_queue.py`

**Purpose:** Database migration script for schema updates and data transformations.

**Usage:**
```bash
python scripts\migrate_feeds_and_queue.py
```

**Use cases:**
- Migrating from old schema to new schema
- Bulk data transformations
- Historical data cleanup

---

## 🔧 Debug & Maintenance Scripts

### `debug_status.py`

**Purpose:** Debug utility for inspecting pipeline status and active episodes.

**Usage:**
```bash
python scripts\debug_status.py
```

**Output:**
- Pipeline running status
- Active episodes count
- Episode completion statistics
- Full JSON status dump

**When to use:**
- Investigating stuck episodes
- Verifying pipeline health
- Debugging status display issues

---

### `reset_stuck_jobs.py`

**Purpose:** Reset episodes stuck in processing states.

**Usage:**
```bash
python scripts\reset_stuck_jobs.py
```

**What it does:**
- Identifies episodes stuck in "transcribing" or "processing" states
- Resets them to "pending" for retry
- Clears stale worker locks

**When to use:**
- After worker crashes
- When episodes are stuck indefinitely
- Before restarting transcription pipeline

---

### `test_events.py`

**Purpose:** Test the Redis Streams event system.

**Usage:**
```bash
python scripts\test_events.py
```

**What it does:**
- Publishes test events to Redis Streams
- Verifies event bus connectivity
- Tests event serialization/deserialization

---

## 📦 Batch Scripts

### `start_listener.bat`

**Purpose:** Windows launcher for the host listener service.

**Features:**
- Auto-installs Python dependencies
- Activates conda environment if available
- Provides clear error messages

---

### `run_bot.bat` ⚠️ DEPRECATED

**Status:** Legacy script, replaced by Docker-based workflow.

**Migration:** Use `start_app.bat` in the project root instead.

---

## 🔄 Auto-Start on Boot (Optional)

To have the listener start automatically:

1. Press `Win+R`, type `shell:startup`, press Enter
2. Create a shortcut to `scripts\start_listener.bat`
3. The service will start when Windows boots

Alternatively, set it up as a Windows Service using tools like NSSM.

---

## 📝 Development Notes

### Adding New Scripts

When adding new utility scripts:

1. Place them in this `scripts/` directory
2. Add documentation to this README
3. Include usage examples and requirements
4. Add error handling and helpful messages
5. Make scripts idempotent when possible

### Script Conventions

- Use `argparse` for command-line arguments
- Include `--help` flag with clear descriptions
- Add logging with appropriate levels
- Handle errors gracefully with user-friendly messages
- Use environment variables from `.env` when needed

