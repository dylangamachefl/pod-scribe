# Docker Secrets Directory

This directory contains sensitive credentials for Docker Secrets.

## Setup Instructions

1. **Add your Gemini API key:**
   ```bash
   echo "your-actual-api-key-here" > gemini_api_key.txt
   ```

2. **Verify the file is gitignored:**
   ```bash
   git status
   # Only README.md and .gitignore should be tracked in secrets/
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

## Security Notes

- ✅ Secret files are gitignored - will NOT be committed
- ✅ Docker Secrets are more secure than environment variables
- ✅ Secrets not visible in `docker inspect` output
- ✅ Secrets not stored in image layers

## File Format

Secret files should contain ONLY the secret value (no quotes, no extra whitespace):
```
your-secret-value-here
```

## Current Secrets

- `gemini_api_key.txt` - Gemini API key for summarization service

## Troubleshooting

**Service won't start:**
- Check that `gemini_api_key.txt` exists and contains your API key
- Verify no extra whitespace or newlines in the file
- Check file permissions (should be readable by Docker)

**Fallback to environment variables:**
If you prefer using `.env` file instead, the service will fall back to `GEMINI_API_KEY` environment variable if the secret file is not found.
